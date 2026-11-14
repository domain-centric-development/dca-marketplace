"""The reviewers' findings as rows the judge reads — one line per finding, from the review files as written.

A review file (`reviews/<perspective>.md`, the review skill's format) carries its findings under `### must-fix`,
`### should-fix` and `### nits`, each a bullet that opens with where it stands in bold, says what is wrong and how to
fix it, and argues why. The judge needs the first three to confirm or drop a finding in the code; the argument it
opens the file for only where a row leaves the question open. The rows are derived, never edited: the files stay
the reviewers' word and the record the document gate reads."""

from __future__ import annotations

import os
import re
import typing

from .delivery_files import REVIEW_RANKS

ROWS_FILE = "findings.md"

_RANK = re.compile(r"^###\s+(must-fix|should-fix|nits?)\b", re.I)
_SECTION = re.compile(r"^##\s")
_BULLET = re.compile(r"^- ")
_WHERE = re.compile(r"^- \*\*(.+?)\*\*\s*(?:\([^)]*\))?\s*[:—–-]*\s*")
_FIX = re.compile(r"\*?Fix:?\*?:?\s*", re.I)
_WHY = re.compile(r"\*?Why:\*?\s*", re.I)
_CAP = 280


def _sentence(text: str) -> str:
    """The first sentence of <text> on one line, capped."""
    flat = " ".join(text.replace("*", "").split())
    found = re.match(r"(.+?[.!?])(?:\s|$)", flat.replace("e.g.", "e\0g\0").replace("i.e.", "i\0e\0"))
    said = (found.group(1) if found else flat).replace("\0", ".")
    return said if len(said) <= _CAP else said[:_CAP - 1].rstrip() + "…"


def _rank_of(heading: str) -> str:
    word = heading.lower()
    return next(rank for rank in REVIEW_RANKS if word.startswith(rank))


def rows_of(text: str) -> typing.List[typing.Tuple[str, str, str]]:
    """The findings of one review file: (rank, where, what and the fix) in the file's order; none where it has none."""
    rows: typing.List[typing.Tuple[str, str, str]] = []
    rank: typing.Optional[str] = None
    bullet: typing.List[str] = []

    def close() -> None:
        if rank and bullet:
            first = bullet[0]
            where = _WHERE.match(first)
            place = where.group(1).replace("`", "") if where else ""
            claim = first[where.end():] if where else first[2:]
            body = " ".join([claim] + [line.strip() for line in bullet[1:]])
            fix = _FIX.split(body, maxsplit=1)
            said = _sentence(_WHY.split(fix[0], maxsplit=1)[0])
            if len(fix) > 1 and fix[1].strip():
                said += f" Fix: {_sentence(fix[1])}"
            rows.append((rank, place, said))
        bullet.clear()

    for line in text.splitlines():
        heading = _RANK.match(line)
        if heading or _SECTION.match(line):
            close()
            rank = _rank_of(heading.group(1)) if heading else None
            continue
        if rank is None:
            continue
        if _BULLET.match(line):
            close()
            bullet.append(line)
        elif bullet and line.strip():
            bullet.append(line)
    close()
    return rows


def write_review_rows(folder: str, perspectives: typing.Sequence[str]) -> typing.Optional[str]:
    """`<folder>/findings.md` from the review files of <perspectives> that exist: a line per finding, the counts per
    perspective first. The path, or None where no review file was written."""
    lines = ["# Findings — one row per finding of the review files beside this one", "",
             "Derived by the runner from `reviews/<perspective>.md`, never edited. A row: perspective · rank · where — "
             "what is wrong. Fix: the reviewer's fix. Open a perspective's file only for a finding whose row does not "
             "carry the question.", ""]
    found = False
    rows: typing.List[str] = []
    for name in perspectives:
        path = os.path.join(folder, f"{name}.md")
        if not os.path.isfile(path):
            lines.append(f"- {name}: no file")
            continue
        found = True
        with open(path, encoding="utf-8") as handle:
            mine = rows_of(handle.read())
        counts = {rank: sum(1 for r in mine if r[0] == rank) for rank in REVIEW_RANKS}
        lines.append(f"- {name}: " + ", ".join(f"{counts[rank]} {rank}" for rank in REVIEW_RANKS)
                     + ("" if mine else " — or a format the rows do not read: open the file"))
        rows += [f"- {name} · {rank} · {where or '—'} — {said}" for rank, where, said in mine]
    if not found:
        return None
    target = os.path.join(folder, ROWS_FILE)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines + [""] + rows).rstrip() + "\n")
    return target
