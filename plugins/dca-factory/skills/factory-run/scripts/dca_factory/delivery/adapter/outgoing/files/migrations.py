"""The layout migrations an update runs, one idempotent move each: a file or folder moved through the repository, the
evidence out of the run folders, the delivered state of a story, the journals read into records, the delivered
stories merged into the living spec, the glossaries out of the code, the method's configuration into one file, and
`migrate_layout` that runs them all in order and prints every move."""

from __future__ import annotations

import contextlib
import glob
import os
import re
import shutil
import time
import typing

from .....contract import CONTRACT
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, evidence_dir, evidence_rel, METHOD_PROFILE, METHOD_ROOT, place, PROFILE_FILE, read_flat, read_profile,
    resolve_profile, set_places, shown)
from .....spec.api import (
    context_folder, derived, merge, read_delta, read_spec, render_spec, story_entries)
from ..git.repository import git
from ..spec.story_spec_files import spec_target, story_spec
from .findings_files import FINDINGS_FILE
from .kept_files import TESTS_BASELINE
from .decision_record_files import record_path
from .owned_files import write_story_fields
from .run_marks import gate_passed_on_record, STORY_DIGEST, write_mark
from .story_layout import (
    journeys_hold, DECISIONS_DIR, delivered_by, delivered_on, find_story, flat_stories, is_delivered, legacy_story_digest, story_digest, STORY_FILE, story_files, story_id_of)
from .story_record import record_story
from .story_runs import PASS_MARKS
from .test_files import read_mapping

Say = typing.Callable[[str], None]


def move_path(cwd: str, src: str, dst: str) -> str:
    """Move a file or folder, through git where it is tracked so history follows; a folder moves whole, the
    untracked files in it included. Returns how."""
    os.makedirs(os.path.dirname(os.path.join(cwd, dst)) or cwd, exist_ok=True)
    tracked = git(cwd, "ls-files", "--error-unmatch", "--", src)[0] == 0
    if tracked and git(cwd, "mv", "-k", "--", src, dst)[0] == 0 and not os.path.lexists(os.path.join(cwd, src)):
        return "git mv"
    shutil.move(os.path.join(cwd, src), os.path.join(cwd, dst))
    return "mv"



def migrate_evidence(cwd: str, runs: str, say: Say) -> None:
    """Each story's evidence out of its run folder (contract 17): `<runs>/<story>/.verify/*` and the marks the gate
    and the runner wrote there move to `<evidence>/<story>/`. Where the evidence folder has one already, the gate
    wrote it since and it is kept; the run folder's older copy goes, and the move says so."""
    if not os.path.isdir(runs):
        return
    for name in sorted(os.listdir(runs)):
        folder = os.path.join(runs, name)
        if not os.path.isdir(folder):
            continue
        evidence = evidence_dir(runs, name)
        verify = os.path.join(folder, ".verify")
        sources = [(os.path.join(verify, entry), os.path.join(evidence, entry))
                   for entry in (sorted(os.listdir(verify)) if os.path.isdir(verify) else [])]
        sources += [(os.path.join(folder, mark), os.path.join(evidence, mark)) for mark in PASS_MARKS
                    if mark not in ("base-tree", "red-tree") and os.path.lexists(os.path.join(folder, mark))]
        if not sources:
            continue
        kept = []
        for src, dst in sources:
            if os.path.lexists(dst):
                kept.append(os.path.basename(src))
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
                continue
            move_path(cwd, src, dst)
        if os.path.isdir(verify) and not os.listdir(verify):
            os.rmdir(verify)
        say(f"{shown(folder)}/ evidence → {shown(evidence)}/"
            + (f" (the evidence folder's own kept, the run folder's dropped: {', '.join(kept)})" if kept else ""))


#: The marks that make a `tasks/<story>/` folder the factory's: without one it is the project's own.
FACTORY_MARKS = (".verify", STORY_DIGEST, ".delivered", ".rounds", ".tests-red", TESTS_BASELINE, ".story-planned")


def adopted_on(run_folder: str, delivered_file: str) -> str:
    """When an adopted story was delivered: the journal's adopt gate, else the mark's own time."""
    journal = os.path.join(run_folder, ".verify", "journal.tsv")
    if os.path.isfile(journal):
        for line in reversed(read_text(journal).splitlines()):
            parts = line.split("\t")
            if len(parts) >= 4 and parts[1] == "gate" and parts[2] == "adopt" and parts[3] == "exit=0":
                return parts[0]
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(delivered_file)))


def migrate_delivery(cwd: str, epics: str, runs: str, say: Say) -> None:
    """The delivered state as contract 18 has it: one end state — an adopted story with a `delivered:` date reads
    `status: delivered` —, a `delivered_by:` line on every delivered story — `gate` where a delivering gate's pass
    is on record (`gate_passed_on_record`), else `hand:unknown`, named; a line a person wrote is left as it is —,
    and the planned digest of a story in flight taken anew with today's `story_digest` where it was taken with the
    old one (contract 17 split on the first `---` anywhere)."""
    for story_path in story_files(epics):
        try:
            front, _body = read_front_matter(story_path)
        except GateError:
            continue
        story_id = story_id_of(story_path)
        status = str(front.get("status", "")).strip().lower()
        if status == "adopted" and delivered_on(front):
            write_story_fields(story_path, status="delivered")
            say(f"{shown(story_path)}: `status: adopted` with a `delivered:` date is `status: delivered` (one end state)")
            front, _body = read_front_matter(story_path)
        if is_delivered(front):
            if not delivered_by(front):
                reason = gate_passed_on_record(cwd, runs, story_id, story_path)
                by = "gate" if reason else "hand:unknown"
                write_story_fields(story_path, delivered_by=by)
                say(f"{shown(story_path)}: `delivered_by: {by}`"
                    + (f" ({reason})" if reason else " — no delivering gate's pass on record; `factory-cli.py "
                                                     f"--prove {story_id}` turns the claim into proof"))
            continue
        planned = os.path.join(evidence_dir(runs, story_id), STORY_DIGEST)
        if os.path.isfile(planned) and read_text(planned).strip() == legacy_story_digest(story_path) \
                and legacy_story_digest(story_path) != story_digest(story_path):
            write_mark(runs, story_id, STORY_DIGEST, story_digest(story_path))
            say(f"{shown(planned)}: the planned digest taken anew with today's function")


def migrate_record(runs: str, say: Say) -> None:
    """WP-150 D: every story's journal becomes its record — the parts and denied calls its streams hold, the signals
    its hand-overs hold, read once with today's parsers and written as journal lines, then the `record` line. A
    journal that is the record is left alone, so a second update writes nothing; a story whose process still runs
    is recorded by a later command."""
    done, partial = 0, []
    ids = {os.path.basename(os.path.dirname(j)) for j in glob.glob(os.path.join(evidence_dir(runs, "*"), "journal.tsv"))}
    ids |= {name for name in (os.listdir(runs) if os.path.isdir(runs) else [])
            if os.path.isdir(os.path.join(runs, name)) and not name.startswith(".")}
    for story_id in sorted(ids):
        with contextlib.suppress(OSError, GateError, ValueError):
            written = record_story(runs, story_id)
            if written is not None:
                done += 1
                if written.get("unknown"):
                    partial.append(f"{story_id} ({written['unknown']})")
    if done:
        say(f"the journal is the record of {done} more stor{'y' if done == 1 else 'ies'} — read once from their streams "
            f"and hand-overs" + (f"; not recorded, its material gone: {', '.join(partial)}" if partial else ""))


def migrate_spec(cwd: str, epics: str, runs: str, say: Say) -> None:
    """The living spec from what is delivered (WP-98): every delivered story merged into its context's spec — or a
    journey item into `journeys.md` — in the order of its `delivered:` time, its test lines from its `tests.md` where
    the run folder kept one; a story without a mapping is merged without test lines and named. Only a criterion the
    spec lacks is merged — and not one a delivered story's plan removed at the same time or later: one the spec holds
    in other words was changed since, one it lacks so was taken out, and taking either back would undo that. A story whose criteria the spec holds already is left alone, so a second run
    changes nothing."""
    delivered = []
    for story_path in story_files(epics):
        try:
            front, body = read_front_matter(story_path)
        except GateError:
            continue
        if is_delivered(front) and spec_target(front):
            delivered.append((delivered_on(front), story_id_of(story_path), story_path, front, body))
    place_of = lambda front: ("journeys" if journeys_hold(front)
                              else str(front.get("context", "")).strip().lower())
    removed: typing.Dict[typing.Tuple[str, str], typing.List[str]] = {}
    for when, story_id, _path, front, _body in delivered:
        plan = os.path.join(runs, story_id, "plan.md")
        if os.path.isfile(plan):
            for key in read_delta(read_text(plan))["removes"]:
                removed.setdefault((place_of(front), key), []).append(when)
    for when, story_id, story_path, front, body in sorted(delivered):
        target, held, _features, _feature = story_spec(front)
        assert target is not None       # the story was listed for its `spec_target`
        preamble, spec = read_spec(target)
        story = story_entries(body)
        # held anywhere in the context — its own file or a feature's (WP-105): a criterion moved into a feature
        # folder is not merged back into the file the story names
        found = derived(story, held)
        story = [item for item in story if found.get(item["key"]) == "adds"
                 and not any(w >= when for w in removed.get((place_of(front), item["key"]), []))]
        if not story:
            continue
        try:
            tests = read_mapping(runs, story_id)[1]
        except GateError:
            tests = {}
        delta = read_delta("")       # what the story's plan changed or removed holds already, or a later story undid it
        title = "Journeys" if journeys_hold(front) else str(front.get("context", "")).strip()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(render_spec(preamble, merge(spec, story, delta, tests), title))
        untested = [item["key"] for item in story if not tests.get(item["key"])]
        say(f"{shown(story_path)} → {shown(target)} ({len(story)} criterion(s))"
            + (f" — without a test line: {', '.join(untested)}" if untested else ""))


#: Where a context's glossary lay beside its domain code before the spec held it.
GLOSSARY_IN_CODE = re.compile(r"(?:^|/)(?:src/(?:main/java/)?)?(?:.*/)?([^/]+)/[Dd]omain/glossary\.md$")


def migrate_glossaries(cwd: str, say: Say) -> None:
    """Each context's glossary out of the code into the spec (WP-98): `<…>/<context>/domain/glossary.md` (Java's
    package path) and `src/<Root>.<Context>/Domain/glossary.md` (.NET) move to `<spec>/<context>/glossary.md`. A spec
    glossary that exists already is kept, and the one in the code named."""
    skip = {"build", "out", "bin", "obj", "target", "node_modules"}
    spec_rel = os.path.relpath(place("spec"), cwd).replace(os.sep, "/")
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        if "glossary.md" not in files:
            continue
        rel = os.path.relpath(os.path.join(root, "glossary.md"), cwd).replace(os.sep, "/")
        if rel.startswith(spec_rel + "/"):
            continue
        match = GLOSSARY_IN_CODE.search(rel)
        if not match:
            continue
        context = match.group(1).rsplit(".", 1)[-1]
        dst = os.path.join(spec_rel, context_folder(context), "glossary.md")
        if os.path.exists(os.path.join(cwd, dst)):
            print(f"migrate: kept {rel} — {dst} exists already")
            continue
        say(f"{rel} → {dst} ({move_path(cwd, rel, dst)})")


#: Where `dca-init` wrote the method's conventions before `dca.profile.yaml` (WP-99).
OLD_CONVENTIONS = (os.path.join(".agents", "dca", "conventions.md"), os.path.join(".claude", "dca", "conventions.md"))


def migrate_configuration(cwd: str, say: Say) -> None:
    """The method's configuration into one file (WP-99): the conventions file's `key: value` lines and the places the
    `AGENTS.md` description section names other than the defaults go into `dca.profile.yaml` — a key the file has
    already is kept —, the old file goes, and the `AGENTS.md` line that pointed at it points at the new one. Once."""
    target = os.path.join(cwd, METHOD_PROFILE)
    have = read_flat(target)
    lines = []
    for rel in OLD_CONVENTIONS:
        path = os.path.join(cwd, rel)
        if not os.path.isfile(path):
            continue
        found, prose = [], []
        for raw in read_text(path).splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key = line.split(":", 1)[0].strip() if ":" in line else ""
            if not key or " " in key:
                prose.append(line)
                continue
            found.append((key, line.split(":", 1)[1].strip()))
        if prose:
            # A file with more than `key: value` lines is a person's: it stays, and the move is named.
            say(f"{rel.replace(os.sep, '/')} kept — it holds lines that are no `key: value` "
                f"({prose[0][:60]!r}); move them into {METHOD_PROFILE} by hand")
            continue
        for key, value in found:
            if key not in have:
                have[key] = value
                lines.append(f"{key}: {value}")
        os.remove(path)
        with contextlib.suppress(OSError):
            os.rmdir(os.path.dirname(path))
        say(f"{rel.replace(os.sep, '/')} → {METHOD_PROFILE} (its lines; the file removed)")
    agents = os.path.join(cwd, "AGENTS.md")
    text = read_text(agents) if os.path.isfile(agents) else ""
    start, end = "<!-- dca-describe: start -->", "<!-- dca-describe: end -->"
    if start in text and end in text:
        block = text.split(start, 1)[1].split(end, 1)[0]
        defaults = {"product": ("overview", METHOD_ROOT + "overview.md"), "tech": ("tech", METHOD_ROOT + "tech.md"),
                    "domain": ("domain", METHOD_ROOT + "domain.md")}
        for key, path in re.findall(r"^\s*-\s*(product|tech|domain):\s*`([^`]+)`", block, re.M):
            method_key, default = defaults[key]
            older = "project/" + ("product.md" if key == "product" else f"{key}.md")
            if path not in (default, older) and method_key not in have:
                have[method_key] = path
                lines.append(f"{method_key}: {path}")
                say(f"AGENTS.md's `- {key}:` place → {METHOD_PROFILE} `{method_key}: {path}`")
    if lines:
        existing = read_text(target) if os.path.isfile(target) else "# The method's configuration — every key optional, the defaults otherwise.\n"
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(existing.rstrip("\n") + "\n" + "\n".join(lines) + "\n")
    pointer = re.compile(r"^- conventions: `[^`]*`.*$", re.M)
    if text and pointer.search(text):
        with open(agents, "w", encoding="utf-8") as handle:
            handle.write(pointer.sub(f"- configuration: `{METHOD_PROFILE}` — the method's places and conventions: layout, "
                                     f"suffixes, the resolved framework configuration", text, count=1))
        say(f"AGENTS.md: the `- conventions:` line points at {METHOD_PROFILE}")


def migrate_layout(cwd: str) -> int:
    """`factory.sh update`'s one move to the layout with one owner per place: the profile to the root
    (`backlog:` → `epics:`), `project/backlog/` → `project/epics/`, each story into a folder of its own with its
    decisions and findings inside, each decision record of the old central store into its story's folder,
    each `tasks/<story>/` that carries factory marks to the run folder, and the delivery mark into the story
    as `status: delivered` + `delivered:`. Idempotent — what is where it belongs is left alone — and every
    move is printed. Anything else under `tasks/` is the project's and is not touched."""
    moved = []

    def say(what: str) -> None:
        moved.append(what)
        print(f"migrate: {what}")

    old_profile = os.path.join(".agents", "factory", "factory.profile.yaml")
    profile_path = resolve_profile(None, cwd)
    moved_profile = False
    if not profile_path and os.path.isfile(old_profile):
        say(f"{old_profile.replace(os.sep, '/')} → {PROFILE_FILE} ({move_path(cwd, old_profile, PROFILE_FILE)})")
        profile_path, moved_profile = PROFILE_FILE, True
    profile = read_profile(profile_path)
    renaming = profile_path and "backlog" in profile and "epics" not in profile
    declared = profile.get("contract", "")
    # The profile is rewritten only where the layout is its subject: the key that named the epics, and the
    # contract line — this layout is what contract 10 describes, so a moved profile says so.
    if renaming or (moved_profile and declared.isdigit() and int(declared) < CONTRACT):
        assert profile_path             # `renaming` and `moved_profile` both stand on a profile that was found
        text = read_text(profile_path)
        changed: typing.List[str] = []
        if renaming:
            value = profile["backlog"]
            renamed = "project/epics" if value.replace("\\", "/").strip("/") == "project/backlog" else value
            text = re.sub(r"^backlog:.*$", f"epics: {renamed}", text, count=1, flags=re.M)
            changed.append(f"`backlog: {value}` is `epics: {renamed}`")
        if declared.isdigit() and int(declared) < CONTRACT:
            text = re.sub(r"^contract:.*$", f"contract: {CONTRACT}", text, count=1, flags=re.M)
            changed.append(f"contract {declared} → {CONTRACT}")
        with open(profile_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        say(f"{profile_path}: " + ", ".join(changed))
        profile = read_profile(profile_path)
    # `project/` → `product/`, `product.md` → `overview.md` (contract 19): the places a profile names under `project/`
    # follow, in the factory's profile and in the method's; a place outside it is the project's own and stays.
    for path in (profile_path, os.path.join(cwd, METHOD_PROFILE)):
        if path and os.path.isfile(path):
            text = read_text(path)
            moved_text = re.sub(r"^(\s*[A-Za-z_.]+:\s*)project/", r"\1product/", text, flags=re.M)
            moved_text = re.sub(r"^(\s*[A-Za-z_.]+:\s*)product/product\.md", r"\1product/overview.md", moved_text, flags=re.M)
            if moved_text != text:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(moved_text)
                say(f"{shown(path)}: places under project/ now under product/")
    profile = read_profile(profile_path)
    set_places(profile)
    if os.path.isdir("project") and place("epics").replace("\\", "/").endswith("product/epics"):
        if not os.path.exists("product"):
            say(f"project/ → product/ ({move_path(cwd, 'project', 'product')})")
        else:
            for name in sorted(os.listdir("project")):
                src, dst = os.path.join("project", name), os.path.join("product", "epics" if name == "backlog" else name)
                if os.path.exists(dst):
                    print(f"migrate: kept {src.replace(os.sep, '/')} — {dst.replace(os.sep, '/')} exists already")
                    continue
                say(f"{src.replace(os.sep, '/')} → {dst.replace(os.sep, '/')} ({move_path(cwd, src, dst)})")
            if not os.listdir("project"):
                os.rmdir("project")
    # The description section of AGENTS.md is the agents' pointer: its places follow the move.
    if os.path.isfile("AGENTS.md") and os.path.isdir("product"):
        text = read_text("AGENTS.md")
        start, end = "<!-- dca-describe: start -->", "<!-- dca-describe: end -->"
        if start in text and end in text:
            head, rest = text.split(start, 1)
            block, tail = rest.split(end, 1)
            moved_block = block.replace("project/product.md", "product/overview.md").replace("`project/", "`product/")
            if moved_block != block:
                with open("AGENTS.md", "w", encoding="utf-8") as handle:
                    handle.write(head + start + moved_block + end + tail)
                say("AGENTS.md: the description section names product/")
    old_overview, overview = os.path.join("product", "product.md"), place("product")
    if os.path.isfile(old_overview) and not os.path.exists(overview) \
            and overview.replace("\\", "/").endswith("product/overview.md"):
        say(f"product/product.md → {shown(overview)} ({move_path(cwd, old_overview, overview)})")
    epics, runs = place("epics"), place("runs")
    old_epics = os.path.join("product", "backlog")
    if os.path.isdir(old_epics) and not os.path.isdir(epics) and epics.replace("\\", "/").endswith(DEFAULTS["epics"]):
        say(f"product/backlog/ → {shown(epics)}/ ({move_path(cwd, old_epics, epics)})")
    # A story is a folder (contract 16): `<epic>/<story>.md` → `<epic>/<story>/story.md`, its `.decisions/`
    # folder → `<story>/decisions/`, its `.findings.md` → `<story>/findings.md`. The folder takes the story's id.
    for src in flat_stories(epics):
        try:
            front, _body = read_front_matter(src)
        except GateError:
            front = {}
        stem = os.path.splitext(os.path.basename(src))[0]
        folder = os.path.join(os.path.dirname(src), str(front.get("id") or "").strip() or stem)
        dst = os.path.join(folder, STORY_FILE)
        if os.path.exists(dst):
            print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
            continue
        say(f"{shown(src)} → {shown(dst)} ({move_path(cwd, src, dst)})")
        for old_name, new_name in ((stem + ".decisions", DECISIONS_DIR), (stem + ".findings.md", FINDINGS_FILE)):
            old_part = os.path.join(os.path.dirname(src), old_name)
            new_part = os.path.join(folder, new_name)
            if not os.path.exists(old_part):
                continue
            if os.path.exists(new_part):
                print(f"migrate: kept {shown(old_part)} — {shown(new_part)} exists already")
                continue
            say(f"{shown(old_part)} → {shown(new_part)} ({move_path(cwd, old_part, new_part)})")
    store = os.path.join(".agents", "factory", "decisions")
    if os.path.isdir(store):
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            src = os.path.join(store, name)
            try:
                front, _body = read_front_matter(src)
                story_id, rid = str(front.get("story", "")).strip(), str(front.get("id", "")).strip()
                story_path = find_story(epics, story_id)
            except GateError as error:
                print(f"migrate: kept {shown(src)} — {error}")
                continue
            if not rid.startswith(story_id + "-"):
                print(f"migrate: kept {shown(src)} — its id {rid!r} does not start with its story {story_id!r}")
                continue
            dst = record_path(story_id, rid, story_path)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)} → {shown(dst)} ({move_path(cwd, src, dst)})")
        if not os.listdir(store):
            os.rmdir(store)
    tasks = "tasks"
    if os.path.isdir(tasks):
        for name in sorted(os.listdir(tasks)):
            src = os.path.join(tasks, name)
            if not os.path.isdir(src) or not any(os.path.exists(os.path.join(src, mark)) for mark in FACTORY_MARKS):
                continue
            dst = os.path.join(runs, name)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)}/ → {shown(dst)}/ ({move_path(cwd, src, dst)})")
            try:
                story_path = find_story(epics, name)
                front, _body = read_front_matter(story_path)
            except GateError:
                continue
            delivered_file = os.path.join(dst, ".delivered")
            if os.path.isfile(delivered_file):
                value = read_text(delivered_file).strip()
                if not is_delivered(front):
                    if value == "adopted":
                        write_story_fields(story_path, status="delivered", delivered=adopted_on(dst, delivered_file))
                    else:
                        write_story_fields(story_path, status="delivered", delivered=value)
                    front, _body = read_front_matter(story_path)
                    say(f"{shown(story_path)} carries the delivery ({value})")
                os.remove(delivered_file)
            digest = os.path.join(dst, STORY_DIGEST)
            if os.path.isfile(digest):
                if not is_delivered(front):
                    write_mark(runs, name, STORY_DIGEST, story_digest(story_path))
                os.remove(digest)
        if not os.listdir(tasks):
            os.rmdir(tasks)
            say("tasks/ removed — it held nothing but the factory's run artefacts")
    migrate_evidence(cwd, runs, say)
    migrate_delivery(cwd, epics, runs, say)
    migrate_configuration(cwd, say)
    migrate_glossaries(cwd, say)
    migrate_spec(cwd, epics, runs, say)
    migrate_record(runs, say)
    attributes = ".gitattributes"
    if os.path.isfile(attributes):
        text = read_text(attributes)
        new_line = f"{evidence_rel()}/**/journal.tsv merge=union"
        old_lines = [line for line in ("tasks/**/.verify/journal.tsv merge=union",
                                       f"{runs}/**/.verify/journal.tsv merge=union") if line in text.splitlines()]
        if old_lines:
            for line in old_lines:
                text = text.replace(line, new_line if new_line not in text else "")
            with open(attributes, "w", encoding="utf-8") as handle:
                handle.write(re.sub(r"\n{2,}", "\n", text))
            say(f"{attributes}: the journals' merge rule follows the evidence folder")
    if not moved:
        print("migrate: nothing to move — the layout is current")
    return 0


def layout_hint(cwd: str, profile: typing.Mapping[str, str]) -> typing.Optional[str]:
    """An older layout, named and never read: `factory.sh update` migrates it. The places this gate reads are
    the profile's and the defaults; a folder from before is not a fallback, because a reader that quietly
    took it would keep two layouts alive."""
    old = []
    if profile.get("backlog") and not profile.get("epics"):
        old.append("`backlog:` in the profile is now `epics:`")
    if os.path.isdir(os.path.join(cwd, "backlog")) and not os.path.isdir(os.path.join(cwd, "project")):
        old.append("backlog/ at the root is now product/epics/ (and backlog/product.md product/overview.md)")
    if os.path.isdir(os.path.join(cwd, "project", "backlog")) and not os.path.isdir(os.path.join(cwd, place("epics"))):
        old.append(f"project/backlog/ is now {place('epics')}/")
    if os.path.isdir(os.path.join(cwd, "project")) and not os.path.isdir(os.path.join(cwd, "product")) \
            and place("epics").replace("\\", "/").endswith("product/epics"):
        old.append("project/ is now product/ (and project/product.md product/overview.md)")
    if os.path.isfile(os.path.join(cwd, ".agents", "factory", "factory.profile.yaml")) \
            and not os.path.isfile(os.path.join(cwd, PROFILE_FILE)):
        old.append(f".agents/factory/factory.profile.yaml is now {PROFILE_FILE} at the project root")
    if os.path.isdir(os.path.join(cwd, ".agents", "factory", "decisions")):
        old.append(f".agents/factory/decisions/ now lives in each story's folder, as <story>/{DECISIONS_DIR}/")
    flat = flat_stories(os.path.join(cwd, place("epics")))
    if flat:
        old.append(f"{len(flat)} story file(s) in the flat layout ({shown(flat[0])}{', …' if len(flat) > 1 else ''}) — "
                   f"a story is a folder now, <epic>/<story>/{STORY_FILE} with its {DECISIONS_DIR}/ and "
                   f"{FINDINGS_FILE} inside")
    tasks = os.path.join(cwd, "tasks")
    if os.path.isdir(tasks) and any(os.path.isdir(os.path.join(tasks, d, ".verify")) or os.path.isfile(os.path.join(tasks, d, ".story-digest"))
                                    for d in os.listdir(tasks)):
        old.append(f"the run artefacts under tasks/ now live under {place('runs')}/ (tasks/ is the project's again)")
    if not old:
        return None
    return "the layout changed — `factory.sh update` migrates it (once, and says what it moved): " + "; ".join(old)
