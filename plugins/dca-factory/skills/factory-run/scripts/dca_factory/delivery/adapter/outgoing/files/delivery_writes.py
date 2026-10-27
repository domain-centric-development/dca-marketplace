"""What a passing gate writes, as files and commits: the plan's marks, the red tree, an acceptance asked, the delivery
into the story, the spec merged, the findings kept, the story's commit on the main line or its claim published."""

from __future__ import annotations

import contextlib
import glob
import os
import re
import subprocess
import time
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    FLAKY_FINDINGS, JOURNAL, evidence_dir, evidence_rel, factory_home, place, places_in, shown)
from .....spec.api import (
    derived, lint_context, merge, merge_context, read_delta, read_spec, render_spec, scenarios_path, story_entries)
from ....domain.model.moment import Moment
from ....domain.model.stage_story import Presence
from ....domain.model.story import StoryId
from ....domain.model.story_state import Detail
from ....domain.service.acceptance_rules import AcceptanceMode, AcceptanceRules
from ..stack.commands import command_for
from ..stack.suite_runs import test_files
from ..claims.remote_claims import PUBLISHED
from ..git.integration import integration_target
from ..git.repository import git, git_identity
from ..spec.story_spec_files import moved_tests, story_spec
from .decision_record_files import ACCEPTANCE_KIND, acceptance_mode, acceptance_records, decisions_store
from .findings_files import (
    PLAIN_COLUMN, append_finding_rows, confirmed_defects, findings_cells, findings_path, open_findings,
    project_findings_head, project_findings_path, record_findings)
from .journal_files import flaky_tests
from .kept_files import RED_TREE, TESTS_BASELINE
from .run_marks import write_mark
from .snapshots import git_tree
from .stage_evidence_files import closed_rows, closes_of
from .story_files import StoryFiles
from .story_layout import journeys_hold, story_digest, story_folder, story_kind
from .test_files import locate_tests, read_mapping
from ....domain.model.stage_story import DONE_ROW, OPEN_ROW
from ....domain.model.verdict import CheckName, FindingState, Said
from ....domain.service.test_verdicts import TestVerdicts

Front = typing.Mapping[str, typing.Any]


def close_findings(result: typing.Any, front: Front) -> None:
    """At a task's delivery: the rows it names under `closes:` set to `done` in their findings.md."""
    closed: typing.List[str] = []
    for row_id in closes_of(front):
        path, row = closed_rows(row_id)
        if not path or row is None or row[6] != OPEN_ROW.value:
            continue
        lines = read_text(path).splitlines()
        for index, line in enumerate(lines):
            cells = findings_cells(line)
            if cells and cells[0] == row[0]:
                cells[-1] = DONE_ROW.value
                lines[index] = "| " + " | ".join(cells) + " |"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        result.written.append(path)
        closed.append(row_id)
    if closed:
        result.ok("findings", f"closed {', '.join(closed)} — set to done in their findings.md")


def record_red_tree(result: typing.Any, cwd: str, runs: str, story_id: str) -> None:
    """At the test gate's pass: the tree as it is, when every mapped test was red in this run. A pass that let a test
    through green — a back round after the build, a decision — has production code past the red state: the tree an
    earlier pass recorded stays, since tidy's tests are laid over it anyway."""
    if any(TestVerdicts.let_through_green(CheckName(c), FindingState(st), Said(m)) is Presence.PRESENT
           for st, c, m in result.entries):
        return
    tree = git_tree(cwd)
    if tree:
        write_mark(runs, story_id, RED_TREE, tree)


def record_tests_baseline(cwd: str, runs: str, story_id: str) -> None:
    """Write the baseline once per story; a later plan gate must not launder a change into it."""
    path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
    if os.path.isfile(path) or git(cwd, "rev-parse", "--git-dir")[0]:
        return
    files = test_files(cwd)
    blobs: typing.List[str] = []
    for rel in files:
        code, blob = git(cwd, "hash-object", "-w", "--", rel)
        if code == 0:
            blobs.append(f"{blob}  {rel}")
    write_mark(runs, story_id, TESTS_BASELINE, "\n".join(blobs))


def acceptance_applies(cwd: str, runs: str, story_id: str, profile: Front) -> bool:
    """Whether this story waits for a human before it is delivered (`AcceptanceRules.asks`)."""
    mode = AcceptanceMode(acceptance_mode(profile))
    browser = str(profile.get("browser", "none")).strip().lower() not in ("", "none")
    end_user = False
    if mode is AcceptanceMode.PAGES and browser:
        with contextlib.suppress(GateError):
            located = locate_tests(cwd, read_mapping(runs, story_id)[1])[0]
            end_user = any(command_for(profile, path)[0] == "e2eTest" for path in located.values())
    return AcceptanceRules.asks(mode, Presence.PRESENT if browser else Presence.ABSENT,
                                Presence.PRESENT if end_user else Presence.ABSENT) is Presence.PRESENT


def ask_acceptance(cwd: str, runs: str, story_id: str, story_path: str, profile: Front,
                   criteria: typing.List[typing.Tuple[str, str]]) -> str:
    """Write the next acceptance record beside the story and return its id. The criteria it lists are the
    ones accepted: a reopen after an acceptance compares the story against them."""
    records = acceptance_records(cwd, story_id, story_path)
    number = len(records) + 1
    rid = f"{story_id}-accept-{number}"
    try:
        _path, mapping = read_mapping(runs, story_id)
    except GateError:
        mapping = {}
    run = str(profile.get("run", "")).strip()
    lines = [f"- {key}: {text}" + (f" — `{', '.join(mapping[key])}`" if mapping.get(key) else "")
             for key, text in criteria]
    store = decisions_store(story_path)
    os.makedirs(store, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(store, f"accept-{number}.md"), "w", encoding="utf-8") as handle:
        handle.write(
            f"---\nid: {rid}\nstory: {story_id}\nstage: document\nkind: {ACCEPTANCE_KIND}\n"
            f"asked: {stamp}\ndigest: {story_digest(story_path)}\n---\n\n"
            f"# Accept {story_id}?\n\n## Question\n"
            f"Every gate passed. Look at what the story delivers before it counts as delivered:\n\n"
            + "\n".join(lines) + "\n\n"
            + (f"Start the application with `{run}`.\n\n" if run else
               "Start the application the way the project runs it (the profile names no `run:`).\n\n")
            + "## Options\n"
              "- accepted: the story is delivered.\n"
              "- a correction: what should be different, written into the story (criteria and an "
              "`answered:` line naming this record); the story runs again from plan.\n")
    return rid


def record_flaky_findings(result: typing.Any, story_path: str, story_id: str, front: Front, runs: str) -> None:
    """WP-113: a test noted flaky in this story and in another one is a finding — a row of the project's own findings
    (`<product>/findings/flaky.md`, WP-146: the flake belongs to no one story), open, for a task (`kind: task`,
    `closes: flaky#<n>`) that fixes the flake instead of running it again for ever. One open row per test across the
    backlog."""
    mine = set(flaky_tests(runs, story_id)) | set(result.flaky)
    root = evidence_dir(runs)
    if not mine or not os.path.isdir(root):
        return
    others: typing.Dict[Detail, typing.List[StoryId]] = {}
    for other in sorted(os.listdir(root)):
        if other != story_id and os.path.isdir(os.path.join(root, other)):
            for test in flaky_tests(runs, other):
                others.setdefault(Detail(test), []).append(StoryId(other))
    open_rows: typing.Set[str] = set()
    with contextlib.suppress(GateError, OSError):
        open_rows = {where for _s, where, _sev, _d, perspective, _f, _p in open_findings(place("epics"))
                     if perspective == "flaky"}
    added = [("flaky", f.test.value, "minor", f.defect.value, f.fix.value, f.plain.value)
             for f in AcceptanceRules.flaky(StoryId(story_id), frozenset(Detail(t) for t in mine),
                                            {t: tuple(s) for t, s in others.items()},
                                            frozenset(Detail(w) for w in open_rows))]
    if added:
        path = project_findings_path(FLAKY_FINDINGS)
        append_finding_rows(path, project_findings_head(FLAKY_FINDINGS), added)
        result.written.append(path)
        result.ok("findings", f"{len(added)} flaky test(s) noted in two stories kept as a finding in "
                              f"{shown(path)}: {', '.join(r[1] for r in added)}")


def integrate_into_home(result: typing.Any, cwd: str, story_path: str, story_id: str, front: Front, runs: str,
                        close: typing.Optional[typing.Callable[[], None]] = None) -> None:
    """Every check holds on the integrated tree: the main checkout takes the story's commit — a fast-forward of
    its branch, nothing else — and the story is delivered. A main checkout on another branch, or with changes
    of its own in a file the commit touches, does not take it: refused (`checkout`), the person decides."""
    home, target = typing.cast(str, factory_home()), integration_target(runs, story_id)
    on = git(home, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip()
    if on != target:
        result.fail("checkout", f"the main checkout is on {on or 'a detached HEAD'}, the story integrates into "
                                f"{target} — switch back, then `factory.sh run --story {story_id} --from integrate`")
        return
    head = git(cwd, "rev-parse", "HEAD")[1].strip()
    done = subprocess.run(["git", "merge", "--ff-only", "--quiet", head], cwd=home, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0 and git(home, "merge-base", "--is-ancestor", "HEAD", head)[0] != 0:
        # The main line moved between the merge and here — a person's commit, another story integrated: the
        # integrate step merges it again and holds the story to the gate once more, as for a target moved earlier.
        result.fail("moved", f"{target} moved on while the story was held to the gate — the integrate step merges "
                             f"again")
        return
    if done.returncode != 0:
        result.fail("checkout", f"the main checkout could not take the story's commit: "
                                f"{(done.stderr or done.stdout).strip().splitlines()[0] if (done.stderr or done.stdout).strip() else 'git refused'}"
                                f" — commit or stash what is in the way there, then "
                                f"`factory.sh run --story {story_id} --from integrate`")
        return
    result.ok("integrated", f"{target} took the story's commit {head[:12]}")
    deliver(result, story_path, story_id, front, runs)
    if not result.failed:
        commit_delivery(result, home, story_id, front, close)


def story_journals(home: str) -> typing.List[str]:
    """The story journals a commit takes along — every one git does not ignore (WP-150: the journal is the record,
    committed): what a delivery and a request wrote into them goes with what they wrote."""
    found: typing.List[str] = []
    for journal in sorted(glob.glob(os.path.join(home, evidence_rel(), "*", JOURNAL))):
        rel = os.path.relpath(journal, home).replace("\\", "/")
        if git(home, "check-ignore", "-q", "--", rel)[0] != 0:
            found.append(rel)
    return found


def commit_delivery(result: typing.Any, home: str, story_id: str, front: Front,
                    close: typing.Optional[typing.Callable[[], None]] = None) -> None:
    """What the delivery wrote on the main line — the story's folder (its state, decisions, findings) and the spec
    it merged — committed there beside the story's commit, so the next story's worktree starts from it. Only those
    paths: what else the main checkout holds, staged or not, stays as it is. `close` writes the delivery's own last
    events first: the commit carries the story's whole record, and nothing of the delivery is written after it."""
    if close:
        close()
    paths: typing.List[str] = []
    for path in dict.fromkeys(result.written):
        rel = os.path.relpath(os.path.abspath(path), home).replace("\\", "/")
        if not rel.startswith("../") and (os.path.exists(os.path.join(home, rel)) or git(home, "ls-files", "--", rel)[1]):
            paths.append(rel)
    paths += story_journals(home)
    if not paths:
        return
    git(home, "add", "-A", "--", *paths)
    if git(home, "diff", "--cached", "--quiet", "HEAD", "--", *paths)[0] == 0:
        return
    scope = re.sub(r"[^a-z0-9]+", "-", str(front.get("context", "")).lower()).strip("-") or "story"
    done = git(home, *git_identity(home), "commit", "--no-verify", "--quiet", "-m",
               f"chore({scope}): deliver {story_id}\n\nStory: {story_id}\n", "--", *paths)
    if done[0] != 0:
        result.fail("committed", f"the delivery's files could not be committed on the main line: {done[1][:300]} — "
                                 f"commit {', '.join(paths)} by hand")
        return
    result.ok("committed", f"the delivery's files committed on the main line: {', '.join(paths)}")


def merge_spec(result: typing.Any, story_path: str, story_id: str, front: Front, runs: str) -> typing.Optional[bool]:
    """The delivering gate's merge (WP-98, WP-105): the story's delta into its context's spec, by key, with the test
    lines from tests.md — the story's criteria into its feature's file, a moved one out of the file it stood in, a
    removed one gone wherever it stood; a feature file left without a criterion goes. Deterministic, nothing a stage
    writes. The story is history from here on."""
    _front, body = read_front_matter(story_path)
    target, spec, _features, feature = story_spec(front)
    if not target:
        return None
    plan = os.path.join(runs, story_id, "plan.md")
    delta = read_delta(read_text(plan)) if os.path.isfile(plan) else read_delta("")
    try:
        mapping = read_mapping(runs, story_id)[1]
    except GateError:
        mapping = {}
    tests = dict(mapping)
    for key, selectors in moved_tests(runs, story_id).items():
        tests.setdefault(key, selectors)        # a criterion of the story keeps the test its mapping names
    story = story_entries(body)
    context = str(front.get("context", "")).strip()
    journey = journeys_hold(front)
    merged = {"": merge(spec, story, delta, tests)} if journey else merge_context(spec, story, delta, tests, feature)
    for entries in merged.values():
        for item in entries:
            if item["key"] in tests and item["key"] not in {s["key"] for s in story}:
                item["tests"] = tests[item["key"]]
    if not journey:
        # The spec as it will stand, checked before a line is written: a delivery never leaves it malformed.
        texts = {name: render_spec(read_spec(scenarios_path(context, name))[0], entries,
                                   f"{context} — {name}" if name else context)
                 for name, entries in merged.items() if entries or not name}
        problems = lint_context(context, texts)
        if problems:
            result.fail("spec", f"the spec after this story would not hold its shape: {'; '.join(problems[:6])}"
                                + (" …" if len(problems) > 6 else "") + " — nothing written")
            return False
    written: typing.List[str] = []
    for name, entries in sorted(merged.items()):
        path = target if journey else scenarios_path(context, name)
        if not entries and name:
            if os.path.isfile(path):
                os.remove(path)
                with contextlib.suppress(OSError):
                    os.rmdir(os.path.dirname(path))
                written.append(f"{shown(path)} (gone — no criterion left)")
                result.written.append(path)
            continue
        if not entries and not os.path.isfile(path):
            continue
        preamble = read_spec(path)[0]
        title = "Journeys" if journey else f"{context} — {name}" if name else context or "Spec"
        text = render_spec(preamble, entries, title)
        if not os.path.isfile(path) or read_text(path) != text:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            written.append(shown(path))
            result.written.append(path)
    found = derived(story, spec)
    result.ok("spec", f"{', '.join(written) or shown(target)}: {sum(v == 'adds' for v in found.values())} added, "
                      f"{sum(v == 'changes' for v in found.values())} changed, {len(delta['removes'])} removed"
                      + (f", {len(delta['moves'])} moved" if delta["moves"] else "")
                      + (f", {len(delta['renames'])} rule(s) renamed" if delta["renames"] else ""))
    return None


def publish_story(result: typing.Any, cwd: str, story_path: str, story_id: str, front: Front, runs: str,
                  config: Front) -> None:
    """WP-93 D: the factory never moves `main`. The delivering function writes into the story's worktree — the story's
    three state lines and the merge into the spec —, the squashed commit takes them, and the story branch is pushed
    with a lease on what this factory pushed last: only its own claim can be overwritten. A person merges it; the
    remote main line then says delivered for every factory."""
    home = factory_home() or cwd
    rel_story = os.path.relpath(story_path, home)
    local_story = os.path.join(cwd, rel_story)
    spec_rel = os.path.relpath(place("spec") if os.path.isabs(place("spec")) else os.path.join(home, place("spec")), home)
    with places_in(cwd):
        before = read_front_matter(local_story)[0]
        mark = os.path.join(evidence_dir(runs, story_id), "published-status")
        with open(mark, "w", encoding="utf-8") as handle:
            handle.write(str(before.get("status", "")).strip() + "\n")
        deliver(result, local_story, story_id, before, runs)
    git(cwd, "add", "-A", "--", spec_rel, os.path.dirname(rel_story))
    if git(cwd, *(["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
                  if not git(cwd, "config", "user.email")[1].strip() else []),
           "commit", "--amend", "--no-edit", "--no-verify", "--quiet")[0] != 0:
        result.fail("published", f"the delivery could not be added to {story_id}'s commit")
        return
    remote, prefix = config["remote"], config["prefix"]
    ref = f"refs/heads/{prefix}{story_id}"
    known = git(cwd, "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{prefix}{story_id}")
    lease = f"--force-with-lease={ref}:{known[1].strip()}" if known[0] == 0 else f"--force-with-lease={ref}:"
    code, out = git(cwd, "push", "--porcelain", lease, remote, f"HEAD:{ref}")
    if code != 0:
        result.fail("published", f"{remote} refused {prefix}{story_id}: {' '.join(out.split())[:300]} — another "
                                 f"factory's commit is there, or a branch rule; needs-human")
        return
    head = git(cwd, "rev-parse", "HEAD")[1].strip()
    with open(os.path.join(evidence_dir(runs, story_id), PUBLISHED), "w", encoding="utf-8") as handle:
        handle.write(head + "\n")
    result.ok("published", f"{prefix}{story_id} on {remote} carries the story as one commit {head[:12]} — delivered on "
                           f"its branch; `main` is not moved: a person merges it (merge request or push)")


def deliver(result: typing.Any, story_path: str, story_id: str, front: Front, runs: str) -> None:
    """The one write a delivering gate makes into a story — the document gate, the adopt gate and, in a story's
    worktree, the integrate gate all call it. One end state: built or adopted, the story reads `status:
    delivered`, `delivered:` and `delivered_by: gate`; an adopted story is no longer `adopted` (that was its
    input: "the code exists, check it"). The judge's confirmed defects that did not block are kept beside it."""
    if story_kind(front) == "task":
        close_findings(result, front)
    elif merge_spec(result, story_path, story_id, front, runs) is False:
        return
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    story = StoryFiles.read(story_path)
    story.deliver_by_gate(Moment(stamp))
    StoryFiles.write(story_path, story)
    result.written.append(story_folder(story_path))
    result.ok("delivered", f"{shown(story_path)} carries `status: delivered`, `delivered: {stamp}`, "
                           f"`delivered_by: gate`")
    added, open_now = record_findings(story_path, story_id, front, runs)
    if added or open_now:
        result.ok("findings", f"{added} confirmed finding(s) kept in {shown(findings_path(story_path))} — "
                              f"{open_now} open there")
    record_flaky_findings(result, story_path, story_id, front, runs)
    judge = os.path.join(runs, story_id, "judge.md")
    unworded = [r[1] for r in confirmed_defects(read_text(judge)) if not r[5]] if os.path.isfile(judge) else []
    if unworded:
        result.note("findings", f"{len(unworded)} confirmed defect(s) in judge.md without `{PLAIN_COLUMN}` "
                                f"({', '.join(unworded[:3])}{' …' if len(unworded) > 3 else ''}) — the one sentence a "
                                f"person reads first; Decide shows the reviewer's `Defect` in its place")
