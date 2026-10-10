"""The files' contract — what a project file says, read one way for every caller.

The places (profile keys, the evidence folder, a story's worktree), front matter, the profile, the story and
epic files, the decision records, the stage table (`STAGES`, one row per stage) and the contract's version.
Nothing here runs a command or decides a stage; the modules above read through these functions, so two callers
can never disagree about what a file says.
"""

import difflib
import hashlib
import os
import re
import subprocess
import time
import typing


EPIC_FIELDS = ("intent", "goal", "metric", "domain_contact")


MAX_ROUNDS = 3


#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools
#: have comparable budgets. Reported as a note, never a failure — the size is not this story's fault.
DOC_BUDGET_BYTES = 32 * 1024


CONTEXT_MAP_CANDIDATES = (
    "project/domain.md",
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)


INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


#: Every place the factory reads and writes, from the profile with its default: the project description
#: and the epics with their stories under `project/` (the people's), the run artefacts under
#: `.dca-factory/` (the run's protocol). The profile itself is the one fixed path — `dca-factory.profile.yaml`
#: at the project root — because it is where the others are read from.
DEFAULTS = {
    "product": "project/product.md",
    "tech": "project/tech.md",
    "domain": "project/domain.md",
    "epics": "project/epics",
    "runs": ".dca-factory/runs",
    "discovery": "project/discovery",
}


PROFILE_FILE = "dca-factory.profile.yaml"


#: The places as this process resolved them once — a flag wins, then the profile's key, then the default —
#: so no reader in the gate, the CLI, the runner or the observer hard-codes one.
PLACES = {}


#: The places as the profile names them, relative to the project — what a story's worktree links to the main
#: checkout's, and what the gate leaves out of a worktree's changes.
PLACES_REL = {}


def set_places(profile, **given):
    PLACES.clear()
    PLACES_REL.clear()
    home = factory_home() if in_worktree() else None
    for key in DEFAULTS:
        relative = str(given.get(key) or "").strip().replace("\\", "/") or location(profile, key)
        PLACES_REL[key] = relative
        PLACES[key] = os.path.join(home, relative).replace("\\", "/") if home and not os.path.isabs(relative) \
            else relative


def place(key):
    return PLACES.get(key) or DEFAULTS[key]


def runs_top():
    """The first segment of the run folder — what a walk over the project leaves out."""
    return place("runs").strip("/").split("/")[0]


# --- a story in a worktree of its own (WP-92) -------------------------------------------------------------
# The runner gives every story a git worktree on a branch of its own, `story/<id>`, under the run folder's
# parent (`.dca-factory/worktrees/<id>`): the story's code lives there until it is integrated, so a story that
# waits — for an answer, for an acceptance — holds no checkout, and several stories run at once. What is state
# stays in the main checkout: the stories with their decisions, the run folder, the profile, the installed
# pipeline and the skills. The worktree sees them through links; a process in the worktree is told the main
# checkout by FACTORY_HOME, and the gate and the CLI read every place from there. Nothing that is state ever
# lands on the story's branch, so no answer and no delivery can fork with it.
HOME_VARIABLE = "FACTORY_HOME"


#: What a worktree links to the main checkout besides the profile's places: the installed pipeline and the
#: tools' skill folders — a link in a skill folder is git-ignored and would be missing from a fresh checkout.
WORKTREE_LINKED = (".agents/factory", ".claude/skills", ".codex/skills", ".opencode/skills", ".agents/skills")


#: Where a story's branch begins its name: `story/<id>`.
STORY_BRANCH = "story/"


def factory_home():
    """The main checkout a process in a story's worktree belongs to, from FACTORY_HOME; None outside one."""
    value = os.environ.get(HOME_VARIABLE, "").strip()
    return os.path.abspath(value) if value else None


def in_worktree(cwd=None):
    """Whether this process works in a story's worktree: FACTORY_HOME names a main checkout other than here."""
    home = factory_home()
    return bool(home) and os.path.realpath(home) != os.path.realpath(cwd or os.getcwd())


def worktree_places():
    """(folders, files) a worktree takes from the main checkout, relative: the epics, the run folder and the
    discovery reports as links with the pipeline and the skill folders; the description and the profile as
    copies, read alone."""
    rel = lambda key: (PLACES_REL.get(key) or DEFAULTS[key]).rstrip("/")
    folders = [rel("epics"), rel("runs"), evidence_rel(), rel("discovery")] + list(WORKTREE_LINKED)
    files = [rel("product"), rel("tech"), rel("domain"), PROFILE_FILE]
    return folders, files


def worktree_owned(path):
    """A path in a worktree that is the main checkout's, not the story's: under a linked place, or a copied file."""
    folders, files = worktree_places()
    return path in files or any(path == f or path.startswith(f + "/") for f in folders)


#: Where the gate and the runner keep what proves a story's work — the journal, the red ledger, the tree snapshots,
#: the changed-files records, the base tree, the story's digest, the round count: beside the run folder, never in
#: it. A stage writes the run folder (its hand-over files); what it is judged by lies where no stage may write.
EVIDENCE = "evidence"


def evidence_rel():
    """The evidence folder relative to the project: beside the run folder."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).rstrip("/")
    return os.path.join(os.path.dirname(runs) or ".dca-factory", EVIDENCE).replace("\\", "/")


def evidence_dir(runs, story_id=None):
    """A story's evidence folder (or the folder of all of them) beside the run folder `runs` — relative or
    absolute as `runs` is."""
    root = os.path.join(os.path.dirname(os.path.normpath(runs)) or ".dca-factory", EVIDENCE)
    return os.path.join(root, story_id) if story_id else root


#: The story's journal: one line per event — `<UTC time>\t<kind>\t<name>\t<field=value>…\tseq=<n>`. The sequence
#: number orders the events, never the clock: two events in one second, a file written in the same second as a gate
#: ran, are told apart by it. The runner, the gate and the cli append through `journal_append`, nothing else writes.
JOURNAL = "journal.tsv"


#: The technical description's headings — the decisions a stage may not take in passing.
TECH_HEADINGS = (
    "Stack",
    "Frontend approach",
    "Persistence",
    "Runtime",
    "Integrations",
    "Version policy",
)


CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*:\s*(\S.*)$")


#: The one scenario per story that shows its value, marked where the story is written: `#### <key> (happy path)`
#: or `- <key> (happy path): <criterion>`. It gets the end-to-end test; the others are integrated.
HAPPY_MARK = re.compile(r"^(?:####\s+|-\s+)([a-z0-9][a-z0-9-]*)\s*\(happy path\)\s*(?::.*)?$")


MAPPING_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|")


SELECTOR = re.compile(r"^([\w.]+)#([\w]+)$")


#: Two different questions, so two different numbers.
#:
#: CONTRACT is the version of the *files* the gate reads and writes: the stack profile's keys, the
#: `gate:tests` table, the red ledger, the shape of a document claim. It goes up only when an older
#: or newer artefact would be read wrongly — that is what makes a mismatch a refusal.
#:
#: VERSION is where this copy came from. The gate is *copied* into a project (`.agents/factory/`),
#: so a project can be governed by a release older than the pipeline it was installed from without
#: anything being incompatible. That is an update to offer, never a reason to refuse, and only the
#: installer can see it — it is the one place that holds both files.
CONTRACT = 17


VERSION = "0.73.3"


def read_front_matter(path):
    """Return (front_matter_dict, body). Values are strings or lists of strings.

    Supports the flat subset the backlog contract prescribes: `key: value` and
    `key:` followed by `- item` lines. Nothing else is interpreted.
    """
    text = read_text(path)
    if not text.startswith("---"):
        raise GateError(f"{path}: no front matter (the file must start with ---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise GateError(f"{path}: front matter is not closed by ---")
    data, key = {}, None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("-", " ", "\t")) and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(line.strip()[1:].strip() if line.strip().startswith("-") else line.strip())
            continue
        if ":" not in line:
            raise GateError(f"{path}: cannot read front-matter line {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        # `key: ""` is YAML for an empty string: read quoted, it would count as a filled field.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
        data[key] = value if value else []
    return data, parts[2]


def unquoted(value):
    """A profile value without the one pair of quotes around it — a quote inside it, at its end too, stays."""
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def read_profile(path):
    """Flat `key: value` profile. Missing file is not an error — every command
    is then reported as not declared."""
    if not path or not os.path.isfile(path):
        return {}
    profile = {}
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        profile[key.strip()] = unquoted(value.strip())
    return profile


#: The profile's schema: every key the gate, the cli, the runner or a stage reads, as written in
#: `templates/factory.profile.yaml.tmpl`. A key outside it is read by nobody, so the contract check names it — a
#: note, never a refusal: a misspelt `requried:` is a check that quietly went, a key from a newer release is one
#: this copy cannot use.
PROFILE_KEYS = frozenset((
    # the commands and how the gate selects and reads a single test
    "compile", "test", "e2eTest", "architecture", "format", "formatFix",
    "filterFlag", "filterFormat", "filterJoin", "testReport", "testEvidence",
    # what the project has, and what must hold
    "required", "browser", "integration", "http.stub", "adopt.breakProof", "acceptance", "run",
    # where things are (DEFAULTS), the generated map and the glossary; `backlog` is the older layout's, named by
    # the layout hint
    *DEFAULTS, "contextMap", "glossary", "backlog",
    # what the stages read and how the runner starts them
    "knowledge", "knowledge.read", "reviews", "stages", "parallel", "stageTimeout", "sessionUsage", "contract",
    # `model` alone is refused by the model check, which names the right form
    "model",
))

#: Key families: `<prefix><name>`, with an open list of names — a test command (`test.integration`), what a
#: command covers (`covers.test`), a carrier (`carrier.build`), a perspective's reviewer (`review.ddd`), a model
#: (`model.claude`, `model.claude.tidy`; the model check holds tool and stage).
PROFILE_FAMILIES = ("test.", "covers.", "carrier.", "review.", "model.")


def unknown_profile_keys(profile):
    """The profile's keys outside the schema, each with the nearest known one where one is close (else None)."""
    unknown = []
    for key in sorted(profile):
        if key in PROFILE_KEYS or any(key.startswith(family) and len(key) > len(family)
                                      for family in PROFILE_FAMILIES):
            continue
        head, dot, tail = key.partition(".")
        family = difflib.get_close_matches(head + ".", PROFILE_FAMILIES, n=1, cutoff=0.75) if dot and tail else []
        near = [family[0] + tail] if family else difflib.get_close_matches(key, PROFILE_KEYS, n=1, cutoff=0.75)
        unknown.append((key, near[0] if near else None))
    return unknown


def read_text(path):
    if not os.path.isfile(path):
        raise GateError(f"{path}: file not found")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class GateError(Exception):
    pass


#: A story is a folder of its own under its epic, `<epics>/<epic>/<story>/`, with everything that belongs to it
#: inside: the story itself, its decision records and acceptances, the judge's findings that did not block.
#: The epic is `<epics>/<epic>/epic.md` beside its story folders — one shape for both, a folder and its file.
STORY_FILE = "story.md"


EPIC_FILE = "epic.md"


DECISIONS_DIR = "decisions"


FINDINGS_FILE = "findings.md"


def story_files(epics):
    """Every story under the epics, sorted: `<epics>/<epic>/<story>/story.md`. A file beside the epics (a
    README) or beside the story folders (`epic.md`) is not a story; a story file of the older flat layout
    (`<epic>/<story>.md`) is not read — `layout_hint` names it and `factory.sh update` moves it."""
    found = []
    if not os.path.isdir(epics):
        return found
    for epic in sorted(os.listdir(epics)):
        folder = os.path.join(epics, epic)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, STORY_FILE)
            if os.path.isfile(path):
                found.append(path)
    return found


def story_folder(story_path):
    """The story's own folder: where its decisions and findings live, and the name its id defaults to."""
    return os.path.dirname(story_path)


def epic_folder(story_path):
    """The folder of the epic a story lies in: the parent of the story's folder."""
    return os.path.dirname(story_folder(story_path))


def flat_stories(epics):
    """Story files of the older flat layout — `<epics>/<epic>/<story>.md` beside `epic.md` — which this gate
    no longer reads."""
    found = []
    if not os.path.isdir(epics):
        return found
    for epic in sorted(os.listdir(epics)):
        folder = os.path.join(epics, epic)
        if os.path.isdir(folder):
            found += [os.path.join(folder, name) for name in sorted(os.listdir(folder))
                      if name.endswith(".md") and name != EPIC_FILE and not name.endswith(".findings.md")
                      and os.path.isfile(os.path.join(folder, name))]
    return found


FINDINGS_HEADER = "| # | Perspective | File:line | Severity | Defect | Fix | Status |"


def findings_path(story_path):
    """The judge's confirmed findings, kept in the story's folder like its decisions: `<story>/findings.md`."""
    return os.path.join(story_folder(story_path), FINDINGS_FILE)


def confirmed_defects(judge_text):
    """The rows of judge.md's `## Confirmed defects` table: (perspective, file:line, severity, defect, fix)."""
    rows, inside = [], False
    for line in judge_text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "confirmed defects"
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() == "perspective" or set(cells[0]) <= set("-: "):
            continue
        rows.append(tuple(cells[:5]))
    return rows


def findings_rows(path):
    """The rows of a findings file: (n, perspective, file:line, severity, defect, fix, status)."""
    rows = []
    if not os.path.isfile(path):
        return rows
    for line in read_text(path).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[0].isdigit():
            rows.append(tuple(cells))
    return rows


def record_findings(story_path, story_id, front, runs):
    """Keep the judge's confirmed defects in the story's folder, as `<story>/findings.md`, when the story is delivered:
    a finding that did not block (a minor) would otherwise live in the run folder alone, which is protocol and
    disposable. One row per finding, `open` until a person or a later story closes it; a row already there
    (same file:line and defect) is not written twice. Returns (added, open)."""
    judge = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(judge):
        return 0, 0
    new = confirmed_defects(read_text(judge))
    path = findings_path(story_path)
    have = findings_rows(path)
    known = {(r[2], r[4]) for r in have}
    added = [r for r in new if (r[1], r[3]) not in known]
    if not have and not added:
        return 0, 0
    if not os.path.isfile(path):
        text = (f"---\nstory: {story_id}\nepic: {front.get('epic', '')}\n---\n\n# Findings — {story_id}\n\n"
                "The judge's confirmed defects that did not block the story, kept for a later story or a person's look. "
                "The pipeline appends; a person sets `Status` to `done` or `wont-fix`.\n\n"
                f"{FINDINGS_HEADER}\n|---|---|---|---|---|---|---|\n")
    else:
        text = read_text(path).rstrip("\n") + "\n"
    n = len(have)
    for perspective, where, severity, defect, fix in added:
        n += 1
        text += f"| {n} | {perspective} | {where} | {severity} | {defect} | {fix} | open |\n"
    if added:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return len(added), sum(1 for r in findings_rows(path) if r[6] == "open")


def open_findings(epics):
    """Every open finding under the epics: (story id, file:line, severity, defect), read from the findings files."""
    out = []
    for story_path in story_files(epics):
        story = story_id_of(story_path)
        out += [(story, r[2], r[3], r[4]) for r in findings_rows(findings_path(story_path)) if r[6] == "open"]
    return out


def story_id_of(path, front=None):
    """A story's id: its front matter's `id:`, else its folder's name."""
    if front is None:
        try:
            front, _ = read_front_matter(path)
        except GateError:
            front = {}
    return str(front.get("id", "")).strip() or os.path.basename(story_folder(path))


def find_story(epics, story_id):
    """The one story file with this id. Two files with one id are refused, naming both: the schedule keys
    stories by id, the run folder and the decisions are named after it, so a second one would silently
    replace the first."""
    wanted, matches = story_id.lower(), []
    for path in story_files(epics):
        if os.path.basename(story_folder(path)).lower() == wanted or story_id_of(path).lower() == wanted:
            matches.append(path)
    if len(matches) > 1:
        raise GateError(f"story id {story_id!r} is not unique — {' and '.join(shown(m) for m in matches)}; "
                        f"an id names one story in the whole project, give one of them another")
    if matches:
        return matches[0]
    flat = [p for p in flat_stories(epics) if os.path.splitext(os.path.basename(p))[0].lower() == wanted]
    if flat:
        raise GateError(f"{shown(flat[0])} is in the older flat layout — a story is a folder now, "
                        f"{epics}/<epic>/<story>/{STORY_FILE}; `factory.sh update` moves it")
    raise GateError(
        f"no story {story_id!r} under {epics}/ — a story is a folder {epics}/<epic>/<story>/ with its "
        f"{STORY_FILE} (front matter, see the backlog contract)"
    )


def duplicate_ids(epics):
    """{id: [paths]} for every id more than one story carries."""
    by_id = {}
    for path in story_files(epics):
        by_id.setdefault(story_id_of(path).lower(), []).append(path)
    return {sid: paths for sid, paths in by_id.items() if len(paths) > 1}


def shown(path):
    """A path as a person reads it — relative to the project, with `/` on every platform. In a story's worktree a
    path of the main checkout's is shown from there: the story, its records, the run folder."""
    home = factory_home()
    if home and in_worktree():
        absolute, here = os.path.abspath(path), os.path.abspath(os.getcwd())
        if absolute.startswith(home + os.sep) and not absolute.startswith(here + os.sep):
            return os.path.relpath(absolute, home).replace(os.sep, "/")
    return os.path.relpath(path).replace(os.sep, "/")


def is_delivered(front):
    """Delivered is a gate's verdict, written into the story: `status: delivered`, or on an adopted story
    (whose status stays `adopted`) a `delivered:` date."""
    return str(front.get("status", "")).strip().lower() == "delivered" or bool(delivered_on(front))


def delivered_on(front):
    value = front.get("delivered", "")
    return value.strip() if isinstance(value, str) else ""


def story_digest(path):
    """The story as planned, `status:` and `delivered:` left out — those two the gate writes, and a delivery
    must not read as "the story changed after it was planned"."""
    text = read_text(path)
    parts = text.split("---", 2)
    if len(parts) >= 3:
        kept = [line for line in parts[1].splitlines()
                if line.split(":", 1)[0].strip().lower() not in ("status", "delivered") or line.startswith((" ", "\t", "-"))]
        text = "---" + "\n".join(kept) + "\n---" + parts[2]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- what is the person's: the story and the answers (WP-94) --------------------------------------------------
# A story's file and every decision's `## Answer` are written by a person — through `/factory-decisions`, by hand —
# and by the gate where it delivers or reopens a story; never by a stage. At a stage window's start the runner (or a
# session's `--stage-start`) records a digest of them; a gate inside the window and the window's end compare. A
# change under a stage is marked (`.owned-changed`) and the story stays stopped until a person looked at it and
# confirms (`factory-cli.py --owned-confirm <story>`). `by:` is free text: the digest is the proof, not the name.
OWNED_DIGEST = ".owned-digest"


#: The hand-overs' digests at a window's start: what the window left as it was.
WINDOW_DIGEST = ".window-digest"


def story_kind(front):
    """`story` (the default), `journey` — a guard over an epic's delivered stories, run as plan, test,
    judge and document, green at its test gate — or `adopt`: a story with `status: adopted` describes
    behaviour the project already has; plan, test and judge map it to green tests, the adopt gate delivers it."""
    if str(front.get("kind", "")).strip().lower() == "journey":
        return "journey"
    if str(front.get("status", "")).strip().lower() == "adopted":
        return "adopt"
    return "story"


def location(profile, key):
    """Where the profile puts one part of the project description, or its default under `project/`."""
    return str(profile.get(key, "")).strip().replace("\\", "/") or DEFAULTS[key]


def layout_hint(cwd, profile):
    """An older layout, named and never read: `factory.sh update` migrates it. The places this gate reads are
    the profile's and the defaults; a folder from before is not a fallback, because a reader that quietly
    took it would keep two layouts alive."""
    old = []
    if profile.get("backlog") and not profile.get("epics"):
        old.append("`backlog:` in the profile is now `epics:`")
    if os.path.isdir(os.path.join(cwd, "backlog")) and not os.path.isdir(os.path.join(cwd, "project")):
        old.append("backlog/ at the root is now project/epics/ (and backlog/product.md project/product.md)")
    if os.path.isdir(os.path.join(cwd, "project", "backlog")) and not os.path.isdir(os.path.join(cwd, place("epics"))):
        old.append(f"project/backlog/ is now {place('epics')}/")
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


def epic_graph(epics):
    """{epic id: [epic ids it depends on]} for every epic under the epics — `depends_on:` in its `epic.md`, the
    same two shapes a story's takes. An epic's id is its `id:`, else its folder's name."""
    graph = {}
    if not os.path.isdir(epics):
        return graph
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, EPIC_FILE)
        if not os.path.isfile(path):
            continue
        try:
            front, _body = read_front_matter(path)
        except GateError:
            front = {}
        graph[str(front.get("id") or name).strip()] = depends_on(front)
    return graph


def epic_order(graph):
    """The epics in dependency order, ties by id; the ones on a cycle last, in id order. An epic named as a
    dependency that does not exist is no node and does not hold anything up here — the check names it."""
    order, placed, remaining = [], set(), sorted(graph)
    while remaining:
        free = [e for e in remaining if all(d in placed or d not in graph for d in graph[e])]
        if not free:
            break
        order.append(free[0])
        placed.add(free[0])
        remaining.remove(free[0])
    return order + remaining, set(remaining)


def epic_dependency_problem(epics, epic):
    """Why an epic's `depends_on:` cannot hold — an unknown epic, itself, a cycle — or None."""
    graph = epic_graph(epics)
    deps = graph.get(epic, [])
    unknown = [d for d in deps if d not in graph]
    if unknown:
        return f"epic {epic!r} depends on {', '.join(repr(d) for d in unknown)}, which is no epic under {epics}/"
    if epic in deps:
        return f"epic {epic!r} depends on itself"
    _order, cycle = epic_order(graph)
    if epic in cycle:
        return f"epic {epic!r} is on a dependency cycle between epics: {', '.join(sorted(cycle))}"
    return None


#: What a table row writes when there is nothing to list: a document stage that changed nothing says
#: so in one row and why, and that row names no file.
NOTHING = {"", "—", "–", "-", "none", "n/a", "nothing"}


# --- decisions: the question a stage may not answer, kept where the answer can land ------------
#
# A stage that cannot decide writes `## needs-human` and the run stops. The question itself lives
# in a record of its own in the story's folder, `<story>/decisions/<nn>.md` with `id: <story>-<nn>` —
# markdown with front matter, committed with the project, in the people's place because the answer
# is a person's — since the stage file has no place for an answer and no second session would find
# one there. State is read from the record, never stored in it: no `## Answer` is open; an
# `## Answer` with `answer:`, `by:` and `at:` is answered; a gate-written `## Applied` is applied.
# A draft that lacks the actor or the time is not an answer — an unconfirmed draft unblocks nothing.
def decisions_store(story_path):
    """The records in the story's folder: `<story>/decisions/` beside its `story.md`."""
    return os.path.join(story_folder(story_path), DECISIONS_DIR)


def records_of(story_id, story_path=None, cwd=None):
    """This story's records, read from the folder beside it — the story found by its id where no path is given,
    under `cwd` where the project is not the working directory (a scratch copy)."""
    if not story_id:
        return []
    epics = os.path.join(cwd, place("epics")) if cwd else place("epics")
    return read_decisions(decisions_store(story_path or find_story(epics, story_id)), story_id)


def record_path(story_id, rid, story_path=None):
    """Where a record with this id lives (or would): `<story>/decisions/<nn>.md` for `id: <story>-<nn>`."""
    store = decisions_store(story_path or find_story(place("epics"), story_id))
    return os.path.join(store, rid[len(story_id) + 1:] + ".md") if rid.startswith(story_id + "-") else os.path.join(store, rid + ".md")


class Stage(typing.NamedTuple):
    """One row of the pipeline. Everything the gate, the cli and the runner know about a stage is here; nothing
    outside the table names a stage to decide on it."""
    name: str
    file: str = ""            #: the hand-over it writes under the run folder ("" — a gate-only step)
    window: str = ""          #: the shared process that may carry it ("builder", "verifier"), "" — its own
    kinds: tuple = ("story",) #: the story kinds that run it (story, journey, adopt)
    gated: bool = True        #: a gate runs for it (`--stage <name>`)
    post_gated: bool = False  #: that gate runs after its file is written, so a pass vouches for the file
    commands: tuple = ()      #: the profile's extra commands its gate runs, in this order; a key not declared is
                              #: skipped and named — a gate failing on a command nobody configured gets switched off
    tested: bool = False      #: its gate runs the mapped tests (red or green) and the checks before them
    red: bool = False         #: a story's mapped tests are red at its gate (a journey's and an adoption's green)
    sizes: tuple = ()         #: the hand-overs whose size its gate weighs against the criteria
    lists: bool = False       #: its hand-over lists the files it changed, and its gate holds it to that list
    guarded: bool = False     #: it writes production code, under the profile's guard skill (`carrier.guard`)
    suite: bool = False       #: its gate runs the policy's required suites whole
    in_order: bool = True     #: a step of the story's run order (adopt and integrate are steps after it)


ALL_KINDS = ("story", "journey", "adopt")


STAGES = (
    Stage("plan", "plan.md", window="builder", kinds=ALL_KINDS),
    Stage("test", "tests.md", window="builder", lists=True, kinds=ALL_KINDS, post_gated=True, tested=True, red=True,
          sizes=("plan.md", "tests.md")),
    Stage("build", "build.md", window="builder", lists=True, guarded=True, post_gated=True, commands=("architecture", "format"),
          tested=True, suite=True, sizes=("build.md",)),
    # The tidy stage changes no behaviour, so its whole claim is that everything still holds: the same commands
    # as the build stage, run again after the refactor.
    Stage("tidy", "tidy.md", window="builder", lists=True, guarded=True, post_gated=True, commands=("architecture", "format"),
          tested=True, suite=True, sizes=("tidy.md",)),
    Stage("judge", "judge.md", window="verifier", kinds=ALL_KINDS, gated=False),
    Stage("document", "document.md", window="verifier", kinds=("story", "journey"), post_gated=True,
          commands=("architecture",), sizes=("judge.md", "document.md")),
    # Nothing built: the adopt gate delivers an adopted story after its judge.
    Stage("adopt", kinds=("adopt",), in_order=False),
    # The story on the main line as it is now: everything the tidy gate holds the story to, once more.
    Stage("integrate", "integrate.md", kinds=ALL_KINDS, commands=("architecture", "format"), tested=True,
          suite=True, in_order=False),
)


STAGE = {stage.name: stage for stage in STAGES}


#: The hand-over each stage of the run order writes.
STAGE_FILES = {s.name: s.file for s in STAGES if s.in_order}


#: One process may carry several stages and mark its window under one name: the shared builder (plan to
#: tidy) and the shared verifier (judge, then document). The journal, the changed-files record and the
#: usage are that window's; every stage still writes its own file.
SHARED_WINDOWS = {w: tuple(s.name for s in STAGES if s.window == w) for w in dict.fromkeys(s.window for s in STAGES if s.window)}


#: Extra profile commands run per stage, in this order.
STAGE_CHECKS = {s.name: s.commands for s in STAGES if s.gated}


#: The stages whose gate runs after their file is written, so a pass of that gate vouches for the file as it stands.
POST_GATED = tuple(s.name for s in STAGES if s.post_gated)


def stage_order(kind="story"):
    """The run order of a story of this kind."""
    return tuple(s.name for s in STAGES if s.in_order and kind in s.kinds)


ANSWER_FIELDS = ("answer", "by", "at")


def section_of(text, heading):
    """The lines under `## <heading>` up to the next `## `, or None when the section is absent."""
    lines, inside, body = text.splitlines(), False, []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if inside:
                break
            inside = stripped[3:].split("(")[0].strip().lower() == heading
            continue
        if inside:
            body.append(line)
    return body if inside or body else None


def fields_of(lines):
    """`key: value` pairs in a section, first occurrence wins."""
    data = {}
    for line in lines or []:
        stripped = line.strip().lstrip("-").strip()
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            data.setdefault(key.strip().lower(), value.strip())
    return data


def decision_state(text):
    """('open' | 'draft' | 'answered' | 'applied', answer fields)."""
    answer = fields_of(section_of(text, "answer"))
    if section_of(text, "applied") is not None:
        return "applied", answer
    if section_of(text, "answer") is None:
        return "open", answer
    if all(answer.get(field) for field in ANSWER_FIELDS):
        return "answered", answer
    return "draft", answer


def read_decisions(store, story_id):
    """[(path, front, body, state, answer)] for every record that names this story, in id order.

    A record the gate cannot read is a refusal, not a skip: a broken record hides a question."""
    if not os.path.isdir(store):
        return []
    records = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(store, name)
        front, body = read_front_matter(path)
        if str(front.get("story", "")).strip() != story_id:
            raise GateError(
                f"{shown(path)}: names story {front.get('story')!r}, but it lies beside {story_id} — a record "
                f"lives in its own story's `{DECISIONS_DIR}/` folder")
        if str(front.get("id", "")).strip() != f"{story_id}-{name[:-3]}":
            raise GateError(
                f"{shown(path)}: `id:` is {front.get('id')!r}, the file is named {name[:-3]!r} — a "
                f"record is found by its file name: `<story>/{DECISIONS_DIR}/<nn>.md` carries `id: <story>-<nn>`")
        state, answer = decision_state(body)
        records.append((path, front, body, state, answer))
    return records


def applying_stage(front, answer):
    """The stage that applies an answer: the one the answer names (`applies: test` — an answer that changes a
    test goes back to the test stage, whoever asked), else the record's `stage:`, the stage that asked."""
    named = str((answer or {}).get("applies", "")).strip().lower()
    return named if named in STAGE_ORDER else str(front.get("stage", "")).strip()


def resume_stage(front, answer):
    """Where the story resumes for an answer: the earlier of the stage that asked and the one the answer
    names. A plan's question answered `applies: test` still re-plans — the plan lists the tests that change —
    and the test stage after it takes the changed expectation."""
    asked, named = str(front.get("stage", "")).strip(), applying_stage(front, answer)
    order = lambda st: STAGE_ORDER.index(st) if st in STAGE_ORDER else len(STAGE_ORDER)
    return min((asked, named), key=order) if asked in STAGE_ORDER else named


def answered_decisions(cwd, story_id, stage):
    """Ids of this story's answered or applied records the given stage applies."""
    try:
        records = records_of(story_id, cwd=cwd)
    except GateError:
        return []
    return [str(front["id"]).strip() for _p, front, _b, state, answer in records
            if state in ("answered", "applied") and applying_stage(front, answer) == stage]


def nothing_line(line):
    """`(none)`, `- None.`, `_None._`, `—` and the like: a line that says there is nothing."""
    text = line.strip().lstrip("-*").strip().strip("_*()").strip().rstrip(".").strip()
    return text.lower() in NOTHING


def needs_human_ids(text):
    """The decision ids a `## needs-human` section names (`decision: <id>`), or [] without one;
    None when the file has no such section at all — or only the heading, left empty or filled with
    `(none)` from the file template: that asks nobody anything, and reading it as a stop halts a
    finished stage."""
    section = section_of(text, "needs-human")
    if section is None or all(nothing_line(line) for line in section):
        return None
    # the id alone: a stage may go on writing after it on the same line ("decision: s-01. The browser …")
    ids = []
    for key, value in fields_of(section).items():
        match = re.match(r"`?([A-Za-z0-9][\w-]*)", value) if key == "decision" and value else None
        if match:
            ids.append(match.group(1))
    return ids


def stamp_applied(path, stage):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"\n## Applied\nat: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                     f"stage: {stage}\n")


def decision_files(cwd):
    """(id from the file name, front, body, state, error, path) for every record of every story, story by
    story in the order of the files."""
    for story_path in story_files(os.path.join(cwd, place("epics"))):
        store = decisions_store(story_path)
        if not os.path.isdir(store):
            continue
        story_id = story_id_of(story_path)
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(store, name)
            try:
                front, body = read_front_matter(path)
            except GateError as error:
                yield f"{story_id}-{name[:-3]}", {}, "", "unreadable", error, path
                continue
            yield f"{story_id}-{name[:-3]}", front, body, decision_state(body)[0], None, path


def git(cwd, *args, env=None):
    try:
        # UTF-8, not the locale: on Windows a cp1252 reading turns an umlaut into another character (a
        # test that did not change looks changed) and raises on bytes like 0x81.
        completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env,
                                   encoding="utf-8", errors="replace")
    except OSError as error:
        return 1, str(error)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
STAGE_ORDER = stage_order("story")


JOURNEY_ORDER = stage_order("journey")                       # nothing to build: the steps are delivered


ADOPT_ORDER = stage_order("adopt")                           # nothing built: the adopt gate delivers it


def depends_on(front):
    """`depends_on: []`, `depends_on: [A, B]` or a `- A` list, as a list of ids."""
    value = front.get("depends_on") or []
    if isinstance(value, str):
        value = [part for part in value.strip().strip("[]").split(",")]
    return [str(part).strip().strip("'\"") for part in value if str(part).strip().strip("'\"")]


def file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def resolve_profile(given, cwd):
    """The stack profile: the one named, else `dca-factory.profile.yaml` at the project root — the one fixed
    path, since every other place is read from it. An older place is not read; `layout_hint` names it."""
    if given:
        return given
    if in_worktree(cwd):
        # in a story's worktree the profile is the main checkout's — the person's, as it is now
        home_profile = os.path.join(factory_home(), PROFILE_FILE)
        return home_profile if os.path.isfile(home_profile) else None
    return PROFILE_FILE if os.path.isfile(os.path.join(cwd, PROFILE_FILE)) else None


#: Checks about how a hand-over is written rather than whether the work is right: a refusal by one of them costs a
#: round without the code being wrong. The journal names every refusal's checks; reports count the two apart.
FORM_CHECKS = ("files-listed", "story-pass", "tests-mapped", "test-titles", "plan-levels", "levels", "documented",
               "decisions", "reviews", "layout")
