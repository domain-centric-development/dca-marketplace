"""A stage's brief as a person or a stage reads it — Markdown — or as a view takes it — JSON."""

from __future__ import annotations

import typing

from ....domain.service.stage_brief import Brief

Model = typing.Dict[str, typing.Any]


def brief_model(brief: Brief) -> Model:
    return dict(
        stage=brief.stage.value, kind=brief.kind.value, about=brief.about.value if brief.about else "",
        said=brief.said.value,
        writes=brief.writes.value if brief.writes else "", window=brief.window.value if brief.window else "",
        told=[dict(rule=t.rule.value, section=t.section.value if t.section else "", words=t.words.value)
              for t in brief.told],
        measured=[dict(rule=m.rule.value, when=m.when.value, refused=m.refused.value if m.refused else "")
                  for m in brief.measured],
        carriers=[dict(role=c.role.value, skill=c.skill.value) for c in brief.carriers])


def markdown(brief: Brief) -> str:
    """The brief in the order a stage works it: what the stage is, the skills it loads, what it is told — every stage's
    frame and its own, each rule's words where its marker stands —, what its gate holds it to."""
    lines = [f"# The {brief.stage.value} stage — a {brief.kind.value}", ""]
    if brief.about:
        lines += [brief.about.value, ""]
    if brief.writes:
        lines += [f"It writes `{brief.writes.value}`" + (f", carried by the shared {brief.window.value}"
                                                         if brief.window else "") + ".", ""]
    if brief.carriers:
        lines += ["## The skills you load", ""]
        lines += [f"- {c.role.value}: the `{c.skill.value}` skill" for c in brief.carriers]
        lines.append("")
    lines += ["## What you do", "", brief.said.value, ""]
    if brief.measured:
        lines += ["## What the gate holds you to", ""]
        lines += [f"- `{m.rule.value}` — when: {m.when.value}" + (f"; refused: {m.refused.value}" if m.refused else "")
                  for m in brief.measured]
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
