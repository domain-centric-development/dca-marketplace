"""A markdown file's text and its front matter — the flat subset every file of the project writes."""

from __future__ import annotations

import os
import typing

#: A front-matter value: a string, or the list of a `key:` followed by `- item` lines.
FrontValue = typing.Union[str, typing.List[str]]
Front = typing.Dict[str, FrontValue]


class MarkdownError(Exception):
    """A project file that cannot be read as the markdown it should be: missing, no front matter, a front-matter line
    that is no `key: value`. The message names the file and says what is wrong."""


#: What the gate calls a project file it cannot read as it should.
GateError = MarkdownError


def read_text(path: str) -> str:
    if not os.path.isfile(path):
        raise MarkdownError(f"{path}: file not found")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def split_front(text: str) -> typing.Optional[typing.Tuple[typing.List[str], str]]:
    """(front lines, body) by lines: the front matter is the lines between a first line `---` and the next line
    `---` — a `---` inside a line is text. None where the text has no closed front matter. The body is everything
    after the closing `---`, its line ending first, as written."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "---":
            return [line.rstrip("\r\n") for line in lines[1:index]], "".join([lines[index][3:]] + lines[index + 1:])
    return None


def read_front_matter(path: str) -> typing.Tuple[Front, str]:
    """Return (front_matter_dict, body). Values are strings or lists of strings.

    Supports the flat subset the backlog contract prescribes: `key: value` and
    `key:` followed by `- item` lines. Nothing else is interpreted.
    """
    text = read_text(path)
    if not text.startswith("---"):
        raise MarkdownError(f"{path}: no front matter (the file must start with ---)")
    split = split_front(text)
    if split is None:
        raise MarkdownError(f"{path}: front matter is not closed by ---")
    front_lines, body = split
    data: Front = {}
    key: typing.Optional[str] = None
    for raw in front_lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("-", " ", "\t")) and key:
            items = data.setdefault(key, [])
            if isinstance(items, list):
                items.append(line.strip()[1:].strip() if line.strip().startswith("-") else line.strip())
            continue
        if ":" not in line:
            raise MarkdownError(f"{path}: cannot read front-matter line {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        # `key: ""` is YAML for an empty string: read quoted, it would count as a filled field.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
        data[key] = value if value else []
    return data, body
