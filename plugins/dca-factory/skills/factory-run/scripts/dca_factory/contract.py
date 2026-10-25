"""The files' contract — what a project file says, read one way for every caller.

The places (profile keys, the evidence folder, a story's worktree), front matter, the profile, the story and
epic files, the decision records, the stage table (`STAGES`, one row per stage) and the contract's version.
Nothing here runs a command or decides a stage; the modules above read through these functions, so two callers
can never disagree about what a file says.
"""

import hashlib
import os
import re
import typing

from .sharedkernel.adapter.outgoing.markdown.front_matter import (
    MarkdownError as GateError, read_front_matter, read_text, split_front)
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    findings_dir, place, PROFILE_FILE, PROJECT_FINDINGS, shown)
from .delivery.application.shared.front import CREATED_KEY
from .delivery.domain.model.stage import PIPELINE, StoryKind, TESTED_KINDS as DOMAIN_TESTED_KINDS, Trait


EPIC_FIELDS = ("intent", "goal", "metric", "domain_contact")


MAX_ROUNDS = 3


#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools
#: have comparable budgets. Reported as a note, never a failure — the size is not this story's fault.
DOC_BUDGET_BYTES = 32 * 1024


CONTEXT_MAP_CANDIDATES = (
    "product/domain.md",
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)


INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


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
CONTRACT = 26


VERSION = "0.94.0"


#: A story is a folder of its own under its epic, `<epics>/<epic>/<story>/`, with everything that belongs to it
#: inside: the story itself, its decision records and acceptances, the judge's findings that did not block.
#: The epic is `<epics>/<epic>/epic.md` beside its story folders — one shape for both, a folder and its file.
STORY_FILE = "story.md"


EPIC_FILE = "epic.md"


#: A story's decision records: `<story>/decisions/` beside its `story.md`.
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


#: The finding as a person reads it first: one short sentence anyone understands at once ("the checkout controller
#: checks the step twice"), beside the reviewer's `Defect` and the `Fix` (contract 23). A judge.md or a findings.md
#: from before it carries no such column and reads with the sentence empty.
PLAIN_COLUMN = "In plain words"
FINDINGS_HEADER = f"| # | Perspective | File:line | Severity | {PLAIN_COLUMN} | Defect | Fix | Status |"
OLD_FINDINGS_HEADER = "| # | Perspective | File:line | Severity | Defect | Fix | Status |"
#: judge.md's `## Confirmed defects` columns as the judge writes them; an older table lacks `In plain words`.
JUDGE_COLUMNS = ("Perspective", "File:line", "Severity", PLAIN_COLUMN, "Defect", "Fix")
JUDGE_HEADER = "| " + " | ".join(JUDGE_COLUMNS) + " |"


def findings_path(story_path):
    """The judge's confirmed findings, kept in the story's folder like its decisions: `<story>/findings.md`."""
    return os.path.join(story_folder(story_path), FINDINGS_FILE)


def confirmed_defects(judge_text):
    """The rows of judge.md's `## Confirmed defects` table: (perspective, file:line, severity, defect, fix, plain).
    The cells are read by the header's names, so a table from before contract 23 — no `In plain words` — reads with
    `plain` empty; a table without a header is read in the old order."""
    rows, inside = [], False
    names = [c.lower() for c in JUDGE_COLUMNS if c != PLAIN_COLUMN]
    for line in judge_text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "confirmed defects"
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0].lower() == "perspective":
            names = [c.lower() for c in cells]
            continue
        if len(cells) < 5 or set(cells[0]) <= set("-: "):
            continue
        cell = dict(zip(names, cells))
        rows.append((cell.get("perspective", ""), cell.get("file:line", ""), cell.get("severity", ""),
                     cell.get("defect", ""), cell.get("fix", ""), cell.get(PLAIN_COLUMN.lower(), "")))
    return rows


def findings_cells(line):
    """A findings row's cells as written, or None for a line that is no row: seven cells before contract 23, eight
    with `In plain words` after `Severity`."""
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells if len(cells) in (7, 8) and cells[0].isdigit() else None


def findings_rows(path):
    """The rows of a findings file: (n, perspective, file:line, severity, defect, fix, status, plain) — `plain`
    empty in a file from before contract 23."""
    rows = []
    if not os.path.isfile(path):
        return rows
    for line in read_text(path).splitlines():
        cells = findings_cells(line)
        if cells is None:
            continue
        if len(cells) == 7:
            rows.append(tuple(cells) + ("",))
        else:
            n, perspective, where, severity, plain, defect, fix, status = cells
            rows.append((n, perspective, where, severity, defect, fix, status, plain))
    return rows


def widen_findings(text):
    """A findings file from before contract 23 in today's shape: the header, its rule and every row gain the empty
    `In plain words` cell after `Severity`, so the rows appended after them stand in one table."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.strip() == OLD_FINDINGS_HEADER:
            lines[index] = FINDINGS_HEADER
            if index + 1 < len(lines) and set(lines[index + 1].strip()) <= set("|-: ") and lines[index + 1].strip():
                lines[index + 1] = "|---|---|---|---|---|---|---|---|"
            continue
        cells = findings_cells(line)
        if cells is not None and len(cells) == 7:
            lines[index] = "| " + " | ".join(cells[:4] + [""] + cells[4:]) + " |"
    return "\n".join(lines)


def record_findings(story_path, story_id, front, runs):
    """Keep the judge's confirmed defects in the story's folder, as `<story>/findings.md`, when the story is delivered:
    a finding that did not block (a minor) would otherwise live in the run folder alone, which is protocol and
    disposable. One row per finding, `open` until a person or a later story closes it; a row already there
    (same file:line and defect) is not written twice. A file from before contract 23 is widened by the plain-words
    column when a row is added to it. Returns (added, open)."""
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
    append_findings(story_path, story_id, front, added)
    return len(added), sum(1 for r in findings_rows(path) if r[6] == "open")


def append_findings(story_path, story_id, front, added):
    """Append rows — (perspective, file:line, severity, defect, fix, plain) — to the story's findings.md, `open`,
    numbered after the rows there; the file is made with its header when it is not there yet."""
    head = (f"---\nstory: {story_id}\nepic: {front.get('epic', '')}\n---\n\n# Findings — {story_id}\n\n"
            "The judge's confirmed defects that did not block the story, kept for a later story or a person's look. "
            "The pipeline appends; a person sets `Status` to `done` or `wont-fix`.\n\n")
    append_finding_rows(findings_path(story_path), head, added)


def append_finding_rows(path, head, added):
    """Append rows — (perspective, file:line, severity, defect, fix, plain) — to a findings file, `open`, numbered
    after the rows there; the file is made with `head` (its front matter, title and sentence) and the table's header
    when it is not there yet."""
    if not added:
        return
    have = findings_rows(path)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        text = head + f"{FINDINGS_HEADER}\n|---|---|---|---|---|---|---|---|\n"
    else:
        text = widen_findings(read_text(path).rstrip("\n")) + "\n"
    n = len(have)
    for perspective, where, severity, defect, fix, plain in added:
        n += 1
        text += f"| {n} | {perspective} | {where} | {severity} | {plain} | {defect} | {fix} | open |\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def project_findings_path(name):
    """`<product>/findings/<name>.md` — a project finding file by its name."""
    return os.path.join(findings_dir(), f"{name}.md")


def project_findings_head(name):
    """The front matter, title and sentence a project finding file is made with."""
    return (f"---\nfindings: {name}\n---\n\n# Findings — {name}\n\n"
            "Findings that belong to no one story, kept for a task or a person's look. The pipeline appends; a person "
            f"sets `Status` to `done` or `wont-fix`, a task closes a row with `closes: {name}#<n>`.\n\n")


def finding_records(epics):
    """Every open finding: a dict with `owner` (the story's id, or a project finding file's name), `row` (`<owner>#<n>`,
    what a task's `closes:` names), `path` (its file), `project` (a project finding, under `<product>/findings/`),
    `where`, `severity`, `defect`, `perspective`, `fix`, `plain` — the stories' first, then the project's."""
    found = []
    def add(owner, path, project):
        for n, perspective, where, severity, defect, fix, status, plain in findings_rows(path):
            if status == "open":
                found.append(dict(owner=owner, row=f"{owner}#{n}", path=path, project=project, where=where,
                                  severity=severity, defect=defect, perspective=perspective, fix=fix, plain=plain))
    for story_path in story_files(epics):
        add(story_id_of(story_path), findings_path(story_path), False)
    folder = os.path.join(os.path.dirname(epics.rstrip("/")) or ".", PROJECT_FINDINGS)
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".md"):
                add(name[:-3], os.path.join(folder, name), True)
    return found


def open_findings(epics):
    """Every open finding under the epics and in the project's findings: (owner, file:line, severity, defect,
    perspective, fix, plain) — `plain` empty for a row from before contract 23."""
    return [(r["owner"], r["where"], r["severity"], r["defect"], r["perspective"], r["fix"], r["plain"])
            for r in finding_records(epics)]


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


def is_delivered(front):
    """Delivered is one state, written into the story: `status: delivered` — by the gate that delivered it, or by
    a person who delivered it by hand (`delivered_by: hand:<who>`). Built or adopted makes no difference once
    delivered (one end state)."""
    return str(front.get("status", "")).strip().lower() == "delivered"


def delivered_on(front):
    value = front.get("delivered", "")
    return value.strip() if isinstance(value, str) else ""


def delivered_by(front):
    """Who claims the delivery: `gate`, `hand:<who>`, or "" for a story delivered before the line existed."""
    value = front.get("delivered_by", "")
    return value.strip() if isinstance(value, str) else ""


#: The lines of a story's front matter the gate and a hand delivery write; a story's digest leaves them out, so
#: a delivery does not read as "the story changed after it was planned".
STATE_KEYS = ("status", "delivered", "delivered_by")


#: When a story or an epic was written: `created:` in its front matter, a UTC time (`2026-10-18T09:12:00Z`; a date
#: alone reads as well). The backlog skill writes it with the item, `update` fills it once from git for an item
#: without it (the commit that added the file). The views order the backlog by it, newest first; an item without it
#: comes last. It says nothing about what the story asks for, so the story's digest leaves it out too.


#: The front-matter lines a story's digest leaves out: its state and when it was written.
DIGEST_LEFT_OUT = STATE_KEYS + (CREATED_KEY,)


def story_digest(path):
    """The story as planned: SHA-256 over the file with LF line endings and the state lines (`STATE_KEYS`) and its
    `created:` line left out — the front matter read by lines (`split_front`), an indented line never a key."""
    text = read_text(path).replace("\r\n", "\n")
    split = split_front(text)
    if split is not None:
        front_lines, body = split
        kept = [line for line in front_lines
                if line.startswith((" ", "\t", "-")) or line.split(":", 1)[0].strip().lower() not in DIGEST_LEFT_OUT]
        text = "---\n" + "".join(line + "\n" for line in kept) + "---" + body
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def legacy_story_digest(path):
    """`story_digest` as contract 17 had it — split on the first `---` anywhere. Read by the migration alone, to
    take a planned story's mark anew with today's function."""
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
    judge and document, green at its test gate —, `task` — a change no actor sees, run as plan, build, tidy, judge
    and document on the existing suite — or `adopt`: a story with `status: adopted` describes behaviour the project
    already has; plan, test and judge map it to green tests, the adopt gate delivers it."""
    named = str(front.get("kind", "")).strip().lower()
    if named in ("journey", "task"):
        return named
    if str(front.get("status", "")).strip().lower() == "adopted":
        return "adopt"
    return "story"


def layout_hint(cwd, profile):
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


class Stage(typing.NamedTuple):
    """One row of the pipeline, flat — the domain's `Stage` in words and flags."""
    name: str
    file: str = ""            #: the hand-over it writes under the run folder ("" — a gate-only step)
    window: str = ""          #: the shared process that may carry it ("builder", "verifier"), "" — its own
    kinds: tuple = ("story",) #: the story kinds that run it (story, journey, adopt, task)
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


#: The kinds of story, in the domain's order.
ALL_KINDS = tuple(kind.value for kind in StoryKind)


#: A task (WP-106) changes nothing an actor sees — a refactoring, a finding without a change of behaviour, a dependency
#: or build change: no criterion, so no test stage; the existing suite, run whole, is its evidence.
TESTED_KINDS = tuple(kind.value for kind in StoryKind if kind in DOMAIN_TESTED_KINDS)


def flat_row(row):
    """A stage of the domain's pipeline as the gate, the runner and the cli read it: words and flags."""
    return Stage(row.name.value, row.hand_over.value if row.hand_over else "",
                 row.window.value if row.window else "", tuple(k.value for k in StoryKind if k in row.kinds),
                 Trait.GATED in row.traits, Trait.POST_GATED in row.traits, tuple(c.value for c in row.commands),
                 Trait.TESTED in row.traits, Trait.RED in row.traits, tuple(h.value for h in row.sizes),
                 Trait.LISTS in row.traits, Trait.GUARDED in row.traits, Trait.SUITE in row.traits,
                 Trait.IN_ORDER in row.traits)


#: The pipeline, one row per stage — the domain's (`delivery/domain/model/stage.py`), in the words the modules not
#: yet moved read.
STAGES = tuple(flat_row(row) for row in PIPELINE)


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


# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
STAGE_ORDER = stage_order("story")


JOURNEY_ORDER = stage_order("journey")                       # nothing to build: the steps are delivered


ADOPT_ORDER = stage_order("adopt")                           # nothing built: the adopt gate delivers it


TASK_ORDER = stage_order("task")                             # nothing new to test: the existing suite holds


def order_for(kind):
    """The run order of a story of this kind, from the stage table."""
    return {"journey": JOURNEY_ORDER, "adopt": ADOPT_ORDER, "task": TASK_ORDER}.get(kind, STAGE_ORDER)


def depends_on(front):
    """`depends_on: []`, `depends_on: [A, B]` or a `- A` list, as a list of ids."""
    value = front.get("depends_on") or []
    if isinstance(value, str):
        value = [part for part in value.strip().strip("[]").split(",")]
    return [str(part).strip().strip("'\"") for part in value if str(part).strip().strip("'\"")]


def file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


#: Checks about how a hand-over is written rather than whether the work is right: a refusal by one of them costs a
#: round without the code being wrong. The journal names every refusal's checks; reports count the two apart.
FORM_CHECKS = ("files-listed", "story-pass", "tests-mapped", "test-titles", "plan-levels", "levels", "documented",
               "decisions", "reviews", "layout")
