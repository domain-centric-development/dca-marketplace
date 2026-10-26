"""A story's spec delta as a person reads it — or as JSON."""

from __future__ import annotations

import json
import typing

Model = typing.Dict[str, typing.Any]


def where(feature: typing.Optional[str]) -> str:
    return feature if feature else "the context" if feature == "" else "—"


def render(view: Model, fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps(view, indent=2)
    lines = [f"spec delta of {view['story']} — {view['context'] or 'no context'}"
             + (f", feature {view['feature']}" if view["feature"] else "")]
    lines += [f"  new feature: {name}" for name in view["features"]]
    for rename in view.get("renames", []):
        lines.append(f'  rule "{rename["old"]}" → "{rename["new"]}"'
                     + (f" — {', '.join(rename['follow'])} follow it" if rename["follow"] else ""))
    for row in view["rows"]:
        if row["verb"] == "holds":
            continue
        head = f"  {row['verb']} {row['key']}"
        if row["verb"] == "moves" or (row["before_feature"] is not None and row["after_feature"] is not None
                                       and row["before_feature"] != row["after_feature"]):
            head += f" ({where(row['before_feature'])} → {where(row['after_feature'])})"
        lines.append(head + (f" — {row['reason']}" if row["reason"] else ""))
        lines += [f"    - {line}" for line in row["before"]]
        lines += [f"    + {line}" for line in row["after"]]
    held = sum(1 for row in view["rows"] if row["verb"] == "holds")
    if held:
        lines.append(f"  {held} criterion(s) hold as they are")
    return "\n".join(lines)
