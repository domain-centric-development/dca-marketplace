"""A markdown body's `## ` sections and the `key: value` lines inside one."""

from __future__ import annotations

import re
import textwrap
import typing


def section_of(text: str, heading: str) -> typing.Optional[typing.List[str]]:
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


def fields_of(lines: typing.Optional[typing.Iterable[str]]) -> typing.Dict[str, str]:
    """`key: value` pairs in a section, first occurrence wins."""
    data: typing.Dict[str, str] = {}
    for line in lines or []:
        stripped = line.strip().lstrip("-").strip()
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            data.setdefault(key.strip().lower(), value.strip())
    return data


def sections_of(body: str, own_block: str, first: typing.Collection[str] = ()
                ) -> typing.Tuple[typing.List[typing.Dict[str, str]], typing.Optional[int]]:
    """Every `## ` section of a story's or an epic's file in the file's order, as {heading, text, kind} — the text
    as Markdown, a wrapped line kept as written, comments left out, an empty section left out. Prose between the
    title and the first section is a section without a heading. The section the detail draws as a block of its own
    (`own_block`) is not among them; `at` says where it stood (the number of sections before it, or None). A section
    named in <first> moves to the front and says so in `kind` — the view draws the sections as given."""
    parts: typing.List[typing.Tuple[str, typing.List[str]]] = []
    heading, lines = "", typing.cast(typing.List[str], [])
    for line in body.splitlines() + ["## "]:
        if line.startswith("## "):
            parts.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif not line.startswith("# "):
            lines.append(line)
    sections: typing.List[typing.Dict[str, str]] = []
    at: typing.Optional[int] = None
    for name, said in parts:
        key = name.split("(")[0].strip().lower()
        if name and key == own_block:
            at = len(sections)
            continue
        text = re.sub(r"\n{3,}", "\n\n", re.sub(r"<!--.*?-->", "", "\n".join(said), flags=re.S)).strip("\n")
        if text.strip():
            sections.append(dict(heading=name, text=textwrap.dedent(text).strip(),
                                 kind=key if name and key in first else ""))
    leading = [s for s in sections if s["kind"]]
    if leading and at is not None:
        at += sum(1 for s in sections[at:] if s["kind"])
    return [*leading, *(s for s in sections if not s["kind"])], at
