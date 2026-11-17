"""The findings as files: the judge's confirmed defects that did not block, kept beside the story
(`<story>/findings.md`), and the project's own (`<product>/findings/<name>.md`) — a table a person sets to `done` or
`wont-fix` and a task closes by its row."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, findings_dir, PROJECT_FINDINGS
from .story_layout import story_files, story_folder, story_id_of
from .diff_lines import added_lines, origin_of
from ....domain.model.backlog_facts import FindingKey, OPEN_ROW
from ....domain.model.story_words import Place
from ....domain.model.finding_class import FindingClass
from ....domain.model.story_state import Detail


FINDINGS_FILE = "findings.md"


#: The finding as a person reads it first: one short sentence anyone understands at once ("the checkout controller
#: checks the step twice"), beside the reviewer's `Defect` and the `Fix` (contract 23). A judge.md or a findings.md
#: from before it carries no such column and reads with the sentence empty.
PLAIN_COLUMN = "In plain words"
#: Where the defect lies — on a line the story added or changed, or on code it did not write — and what became of it,
#: both the pipeline's (contract 37); `Status` stays the person's.
ORIGIN_COLUMN = "Origin"
OUTCOME_COLUMN = "Outcome"
#: A finding's class, ODC's closer in short (contract 39): what had to change, the kind of correction, and whether
#: something was missing, wrong or too much — the judge's, read by the lessons (`finding_class.py`).
CLASS_COLUMNS = ("Target", "Type", "Qualifier")
FINDINGS_HEADER = (f"| # | Perspective | File:line | Severity | {ORIGIN_COLUMN} | {OUTCOME_COLUMN} | {PLAIN_COLUMN} | Defect "
                   f"| Fix | Status | Target | Type | Qualifier |")
FINDINGS_RULE = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
CLASSLESS_FINDINGS_HEADER = (f"| # | Perspective | File:line | Severity | {ORIGIN_COLUMN} | {OUTCOME_COLUMN} | "
                             f"{PLAIN_COLUMN} | Defect | Fix | Status |")
PLAIN_FINDINGS_HEADER = f"| # | Perspective | File:line | Severity | {PLAIN_COLUMN} | Defect | Fix | Status |"
OLD_FINDINGS_HEADER = "| # | Perspective | File:line | Severity | Defect | Fix | Status |"
#: The origin an old row reads with: before contract 37 every confirmed blocking defect sent the story back.
OLD_ORIGIN = "introduced"
#: judge.md's `## Confirmed defects` columns as the judge writes them; an older table lacks `In plain words` and,
#: before contract 39, the class.
JUDGE_COLUMNS = ("Perspective", "File:line", "Severity", *CLASS_COLUMNS, PLAIN_COLUMN, "Defect", "Fix")
JUDGE_HEADER = "| " + " | ".join(JUDGE_COLUMNS) + " |"


def findings_path(story_path: str) -> str:
    """The judge's confirmed findings, kept in the story's folder like its decisions: `<story>/findings.md`."""
    return os.path.join(story_folder(story_path), FINDINGS_FILE)


def confirmed_defects(judge_text: str) -> typing.List[typing.Tuple[str, ...]]:
    """The rows of judge.md's `## Confirmed defects` table: (perspective, file:line, severity, defect, fix, plain).
    The cells are read by the header's names, so a table from before contract 23 — no `In plain words` — reads with
    `plain` empty; a table without a header is read in the old order."""
    rows: typing.List[typing.Tuple[str, ...]] = []
    inside = False
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


def confirmed_classes(judge_text: str) -> typing.List[typing.Tuple[str, str, str]]:
    """The class cells of each confirmed defect, in `confirmed_defects`' order: (target, type, qualifier) as written,
    empty where the table has no such column (before contract 39)."""
    found: typing.List[typing.Tuple[str, str, str]] = []
    inside = False
    names = [c.lower() for c in JUDGE_COLUMNS if c != PLAIN_COLUMN and c not in CLASS_COLUMNS]
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
        found.append((cell.get("target", ""), cell.get("type", ""), cell.get("qualifier", "")))
    return found


def findings_cells(line: str) -> typing.Optional[typing.List[str]]:
    """A findings row's cells as written, or None for a line that is no row: seven cells before contract 23, eight
    with `In plain words` after `Severity`, ten with `Origin` and `Outcome` before it (contract 37), thirteen with the
    class at the end (contract 39)."""
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells if len(cells) in (7, 8, 10, 13) and cells[0].isdigit() else None


def row_class(row: typing.Sequence[str]) -> typing.Optional[FindingClass]:
    """A findings row's class — the one way every reader takes it (the status, learning, the classify request): the three
    cells at its end, each of its list; None for a row without one, or `—` where no value fitted."""
    return FindingClass.written(Detail(row[10]), Detail(row[11]), Detail(row[12])) if len(row) > 12 else None


def classed_rows(path: str) -> typing.List[typing.Tuple[typing.Tuple[str, ...], FindingClass]]:
    """The rows of a findings file that carry a class, with it."""
    found = []
    for row in findings_rows(path):
        kind = row_class(row)
        if kind is not None:
            found.append((row, kind))
    return found


def findings_rows(path: str) -> typing.List[typing.Tuple[str, ...]]:
    """The rows of a findings file: (n, perspective, file:line, severity, defect, fix, status, plain, origin, outcome,
    target, type, qualifier) — `plain` empty in a file from before contract 23, `origin` `introduced` and `outcome`
    empty before 37, the class empty before 39."""
    rows: typing.List[typing.Tuple[str, ...]] = []
    if not os.path.isfile(path):
        return rows
    for line in read_text(path).splitlines():
        cells = findings_cells(line)
        if cells is None:
            continue
        if len(cells) == 7:
            rows.append(tuple(cells) + ("", OLD_ORIGIN, "", "", "", ""))
        elif len(cells) == 8:
            n, perspective, where, severity, plain, defect, fix, status = cells
            rows.append((n, perspective, where, severity, defect, fix, status, plain, OLD_ORIGIN, "", "", "", ""))
        else:
            n, perspective, where, severity, origin, outcome, plain, defect, fix, status = cells[:10]
            target, kind, qualifier = cells[10:13] if len(cells) == 13 else ("", "", "")
            rows.append((n, perspective, where, severity, defect, fix, status, plain, origin, outcome, target, kind,
                         qualifier))
    return rows


def widen_findings(text: str) -> str:
    """A findings file from before contract 39 in today's shape: the header, its rule and every row gain `Origin` —
    `introduced`, as every blocking defect was read then — and an empty `Outcome` after `Severity`, a file from
    before contract 23 the empty `In plain words` cell, and every row the three empty class cells at its end, so the
    rows appended after them stand in one table."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.strip() in (OLD_FINDINGS_HEADER, PLAIN_FINDINGS_HEADER, CLASSLESS_FINDINGS_HEADER):
            lines[index] = FINDINGS_HEADER
            if index + 1 < len(lines) and set(lines[index + 1].strip()) <= set("|-: ") and lines[index + 1].strip():
                lines[index + 1] = FINDINGS_RULE
            continue
        cells = findings_cells(line)
        if cells is not None and len(cells) == 7:
            lines[index] = "| " + " | ".join(cells[:4] + [OLD_ORIGIN, "", ""] + cells[4:] + ["", "", ""]) + " |"
        elif cells is not None and len(cells) == 8:
            lines[index] = "| " + " | ".join(cells[:4] + [OLD_ORIGIN, ""] + cells[4:] + ["", "", ""]) + " |"
        elif cells is not None and len(cells) == 10:
            lines[index] = "| " + " | ".join(cells + ["", "", ""]) + " |"
    return "\n".join(lines)


def record_findings(story_path: str, story_id: str, front: typing.Mapping[str, typing.Any], runs: str) -> typing.Tuple[int, int]:
    """Keep the judge's confirmed defects in the story's folder, as `<story>/findings.md`, when the story is delivered:
    a finding that did not block (a minor) would otherwise live in the run folder alone, which is protocol and
    disposable. One row per finding, `open` until a person or a later story closes it; a row already there
    (same file:line and defect) is not written twice. A file from before contract 23 is widened by the plain-words
    column when a row is added to it. Returns (added, open)."""
    judge = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(judge):
        return 0, 0
    diff_path = os.path.join(evidence_dir(runs, story_id), "story.diff")
    diff = read_text(diff_path) if os.path.isfile(diff_path) else None
    added_by = added_lines(diff) if diff is not None and not diff.startswith("# no diff") else None
    text = read_text(judge)
    new = [row + (origin_of(row[1], added_by).value if added_by is not None else "", "") + kind
           for row, kind in zip(confirmed_defects(text), confirmed_classes(text))]
    path = findings_path(story_path)
    have = findings_rows(path)
    known = {FindingKey(Place(r[2]), Detail(r[4])) for r in have}
    key = lambda row: FindingKey(Place(row[1]), Detail(row[3]))
    added = [r for r in new if key(r) not in known]
    if not have and not added:
        return 0, 0
    append_findings(story_path, story_id, front, added)
    return len(added), sum(1 for r in findings_rows(path) if r[6] == OPEN_ROW.value)


def append_findings(story_path: str, story_id: str, front: typing.Mapping[str, typing.Any],
                    added: typing.Sequence[typing.Tuple[str, ...]]) -> None:
    """Append rows — (perspective, file:line, severity, defect, fix, plain) — to the story's findings.md, `open`,
    numbered after the rows there; the file is made with its header when it is not there yet."""
    head = (f"---\nstory: {story_id}\nepic: {front.get('epic', '')}\n---\n\n# Findings — {story_id}\n\n"
            "The judge's confirmed defects that did not block the story, kept for a later story or a person's look. "
            "The pipeline appends; a person sets `Status` to `done` or `wont-fix`.\n\n")
    append_finding_rows(findings_path(story_path), head, added)


def append_finding_rows(path: str, head: str, added: typing.Sequence[typing.Tuple[str, ...]]) -> None:
    """Append rows — (perspective, file:line, severity, defect, fix, plain) — to a findings file, `open`, numbered
    after the rows there; the file is made with `head` (its front matter, title and sentence) and the table's header
    when it is not there yet."""
    if not added:
        return
    have = findings_rows(path)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        text = head + f"{FINDINGS_HEADER}\n{FINDINGS_RULE}\n"
    else:
        text = widen_findings(read_text(path).rstrip("\n")) + "\n"
    n = len(have)
    for row in added:
        perspective, where, severity, defect, fix, plain = row[:6]
        origin = row[6] if len(row) > 6 else ""
        outcome = row[7] if len(row) > 7 else ""
        target, kind, qualifier = row[8:11] if len(row) > 10 else ("", "", "")
        n += 1
        text += (f"| {n} | {perspective} | {where} | {severity} | {origin} | {outcome} | {plain} | {defect} | {fix} "
                 f"| open | {target} | {kind} | {qualifier} |\n")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def project_findings_path(name: str) -> str:
    """`<product>/findings/<name>.md` — a project finding file by its name."""
    return os.path.join(findings_dir(), f"{name}.md")


def project_findings_head(name: str) -> str:
    """The front matter, title and sentence a project finding file is made with."""
    return (f"---\nfindings: {name}\n---\n\n# Findings — {name}\n\n"
            "Findings that belong to no one story, kept for a task or a person's look. The pipeline appends; a person "
            f"sets `Status` to `done` or `wont-fix`, a task closes a row with `closes: {name}#<n>`.\n\n")


def finding_records(epics: str) -> typing.List[typing.Dict[str, typing.Any]]:
    """Every open finding: a dict with `owner` (the story's id, or a project finding file's name), `row` (`<owner>#<n>`,
    what a task's `closes:` names), `path` (its file), `project` (a project finding, under `<product>/findings/`),
    `where`, `severity`, `defect`, `perspective`, `fix`, `plain` — the stories' first, then the project's."""
    found: typing.List[typing.Dict[str, typing.Any]] = []

    def add(owner: str, path: str, project: bool) -> None:
        for n, perspective, where, severity, defect, fix, status, plain, origin, outcome, *_kind in findings_rows(path):
            if status == OPEN_ROW.value and outcome in ("", "dropped"):
                found.append(dict(owner=owner, row=f"{owner}#{n}", path=path, project=project, where=where,
                                  severity=severity, defect=defect, perspective=perspective, fix=fix, plain=plain,
                                  origin=origin, outcome=outcome))
    for story_path in story_files(epics):
        add(story_id_of(story_path), findings_path(story_path), False)
    folder = os.path.join(os.path.dirname(epics.rstrip("/")) or ".", PROJECT_FINDINGS)
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".md"):
                add(name[:-3], os.path.join(folder, name), True)
    return found


def open_findings(epics: str) -> typing.List[typing.Tuple[str, ...]]:
    """Every open finding under the epics and in the project's findings: (owner, file:line, severity, defect,
    perspective, fix, plain) — `plain` empty for a row from before contract 23."""
    return [(r["owner"], r["where"], r["severity"], r["defect"], r["perspective"], r["fix"], r["plain"])
            for r in finding_records(epics)]
