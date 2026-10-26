"""The findings as files: the judge's confirmed defects that did not block, kept beside the story
(`<story>/findings.md`), and the project's own (`<product>/findings/<name>.md`) — a table a person sets to `done` or
`wont-fix` and a task closes by its row."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import findings_dir, PROJECT_FINDINGS
from .story_layout import story_files, story_folder, story_id_of
from ....domain.model.stage_story import FindingKey, OPEN_ROW, Place
from ....domain.model.story_state import Detail
from ....domain.service.finding_rules import FindingRules


FINDINGS_FILE = "findings.md"


#: The finding as a person reads it first: one short sentence anyone understands at once ("the checkout controller
#: checks the step twice"), beside the reviewer's `Defect` and the `Fix` (contract 23). A judge.md or a findings.md
#: from before it carries no such column and reads with the sentence empty.
PLAIN_COLUMN = "In plain words"
FINDINGS_HEADER = f"| # | Perspective | File:line | Severity | {PLAIN_COLUMN} | Defect | Fix | Status |"
OLD_FINDINGS_HEADER = "| # | Perspective | File:line | Severity | Defect | Fix | Status |"
#: judge.md's `## Confirmed defects` columns as the judge writes them; an older table lacks `In plain words`.
JUDGE_COLUMNS = ("Perspective", "File:line", "Severity", PLAIN_COLUMN, "Defect", "Fix")
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


def findings_cells(line: str) -> typing.Optional[typing.List[str]]:
    """A findings row's cells as written, or None for a line that is no row: seven cells before contract 23, eight
    with `In plain words` after `Severity`."""
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells if len(cells) in (7, 8) and cells[0].isdigit() else None


def findings_rows(path: str) -> typing.List[typing.Tuple[str, ...]]:
    """The rows of a findings file: (n, perspective, file:line, severity, defect, fix, status, plain) — `plain`
    empty in a file from before contract 23."""
    rows: typing.List[typing.Tuple[str, ...]] = []
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


def widen_findings(text: str) -> str:
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


def record_findings(story_path: str, story_id: str, front: typing.Mapping[str, typing.Any], runs: str) -> typing.Tuple[int, int]:
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
    known = {FindingKey(Place(r[2]), Detail(r[4])) for r in have}
    key = lambda row: FindingKey(Place(row[1]), Detail(row[3]))
    kept = FindingRules.kept(known, [key(r) for r in new])
    added = [r for r in new if key(r) in kept]
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
        text = head + f"{FINDINGS_HEADER}\n|---|---|---|---|---|---|---|---|\n"
    else:
        text = widen_findings(read_text(path).rstrip("\n")) + "\n"
    n = len(have)
    for perspective, where, severity, defect, fix, plain in added:
        n += 1
        text += f"| {n} | {perspective} | {where} | {severity} | {plain} | {defect} | {fix} | open |\n"
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
        for n, perspective, where, severity, defect, fix, status, plain in findings_rows(path):
            if status == OPEN_ROW.value:
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


def open_findings(epics: str) -> typing.List[typing.Tuple[str, ...]]:
    """Every open finding under the epics and in the project's findings: (owner, file:line, severity, defect,
    perspective, fix, plain) — `plain` empty for a row from before contract 23."""
    return [(r["owner"], r["where"], r["severity"], r["defect"], r["perspective"], r["fix"], r["plain"])
            for r in finding_records(epics)]
