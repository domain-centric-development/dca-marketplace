"""A markdown body's `## ` sections and the `key: value` lines inside one."""

from __future__ import annotations

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
