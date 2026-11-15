"""The lines a story's diff adds or changes, and a judge row's origin against them: on a line the story added or
changed (`introduced`), on code it did not write (`pre-existing`), or at a place no line names (unresolved)."""

from __future__ import annotations

import re
import typing

from ....domain.model.judge_rows import Origin

#: A file's header in a git diff, and a hunk's header with the new side's first line.
FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
#: A row's place: a path, a colon, a line.
PLACE = re.compile(r"([^\s`:|]+?\.[A-Za-z]\w*):(\d+)")


def added_lines(diff: str) -> typing.Dict[str, typing.Set[int]]:
    """{path: the new side's line numbers the diff adds or changes} — a file the diff creates has every line added."""
    found: typing.Dict[str, typing.Set[int]] = {}
    path: typing.Optional[str] = None
    line = 0
    for text in diff.splitlines():
        header = FILE_HEADER.match(text)
        if header:
            path = header.group(1).strip()
            found.setdefault(path, set())
            continue
        if text.startswith("diff --git ") or text.startswith("--- "):
            continue
        hunk = HUNK.match(text)
        if hunk:
            line = int(hunk.group(1))
            continue
        if path is None or not line:
            continue
        if text.startswith("+"):
            found[path].add(line)
            line += 1
        elif text.startswith("-"):
            continue
        else:
            line += 1
    return found


def origin_of(where: str, added: typing.Mapping[str, typing.Set[int]]) -> Origin:
    """The origin of a row's place against the diff's added lines; a path matches a diff path it ends with or that
    ends with it, so a row may name the file from the project root or by a shorter tail."""
    found = PLACE.search(where.replace("`", ""))
    if not found:
        return Origin.UNRESOLVED
    path, number = found.group(1).replace("\\", "/").lstrip("./"), int(found.group(2))
    for diffed, lines in added.items():
        if diffed == path or diffed.endswith("/" + path) or path.endswith("/" + diffed):
            return Origin.INTRODUCED if number in lines else Origin.PRE_EXISTING
    return Origin.PRE_EXISTING


def added_texts(diff: str) -> typing.Dict[str, typing.Dict[int, str]]:
    """{path: {new-side line: its text}} for every line the diff adds or changes."""
    found: typing.Dict[str, typing.Dict[int, str]] = {}
    path: typing.Optional[str] = None
    line = 0
    for text in diff.splitlines():
        header = FILE_HEADER.match(text)
        if header:
            path = header.group(1).strip()
            found.setdefault(path, {})
            continue
        if text.startswith("diff --git ") or text.startswith("--- "):
            continue
        hunk = HUNK.match(text)
        if hunk:
            line = int(hunk.group(1))
            continue
        if path is None or not line:
            continue
        if text.startswith("+"):
            found[path][line] = text[1:]
            line += 1
        elif not text.startswith("-"):
            line += 1
    return found


def place_of(where: str) -> typing.Optional[typing.Tuple[str, int]]:
    """(path, line) of a row's place, or None."""
    found = PLACE.search(where.replace("`", ""))
    return (found.group(1).replace("\\", "/").lstrip("./"), int(found.group(2))) if found else None


def changed_since(where: str, now: typing.Mapping[str, typing.Mapping[int, str]],
                  before: typing.Mapping[str, typing.Mapping[int, str]]) -> bool:
    """Whether the row's line is one the story added or changed since the earlier diff — added now, and its text not
    among the lines the earlier diff added to that file."""
    place = place_of(where)
    if place is None:
        return False
    path, number = place
    for diffed, lines in now.items():
        if diffed == path or diffed.endswith("/" + path) or path.endswith("/" + diffed):
            if number not in lines:
                return False
            earlier = next((set(t.values()) for p, t in before.items()
                            if p == diffed or p.endswith("/" + path) or path.endswith("/" + p)), set())
            return lines[number] not in earlier
    return False
