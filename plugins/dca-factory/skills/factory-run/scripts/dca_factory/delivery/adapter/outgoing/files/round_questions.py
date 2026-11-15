"""A round's questions against the judge's verdict: the defects the judge confirmed (`judge.md`, `## Confirmed
defects`) and the places an open stage question cites — each place by file name and line, so `src/…/Order.java:38`
and `Order.java:38` are one."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text

#: A cited place: a file with an extension, a colon, a line.
CITED = re.compile(r"([\w./\\-]+\.[A-Za-z]\w*):(\d+)")
#: The judge's verdict line.
VERDICT = re.compile(r"^\s*verdict:\s*`?([\w-]+)", re.M)


def place_key(text: str) -> str:
    """`<file name>:<line>` of a cited place."""
    found = CITED.search(text.replace("`", ""))
    return f"{os.path.basename(found.group(1).replace(chr(92), '/'))}:{found.group(2)}" if found else ""


def judge_sent_back(runs: str, story_id: str) -> bool:
    """Whether the judge's last verdict sent the story back."""
    path = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(path):
        return False
    found = VERDICT.search(read_text(path))
    return bool(found) and found.group(1).lower() != "pass"


def judged_defects(runs: str, story_id: str) -> typing.List[typing.Tuple[str, str]]:
    """(place, severity) for each row of the judge's `## Confirmed defects` table."""
    path = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(path):
        return []
    lines = section_of(read_text(path), "confirmed defects") or []
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines if line.strip().startswith("|")]
    if not rows:
        return []
    head = [c.lower() for c in rows[0]]
    where = next((i for i, c in enumerate(head) if "file" in c or "where" in c), None)
    severity = next((i for i, c in enumerate(head) if "severity" in c or "rank" in c), None)
    if where is None or severity is None:
        return []
    found = []
    for row in rows[1:]:
        if len(row) <= max(where, severity) or set(row[0]) <= set("-: "):
            continue
        key = place_key(row[where])
        if key:
            found.append((key, row[severity].strip("` *").lower()))
    return found


def cited_places(body: str) -> typing.List[str]:
    """The places a record's text cites, each once, by file name and line."""
    keys = []
    for match in CITED.finditer(body.replace("`", "")):
        key = f"{os.path.basename(match.group(1).replace(chr(92), '/'))}:{match.group(2)}"
        if key not in keys:
            keys.append(key)
    return keys
