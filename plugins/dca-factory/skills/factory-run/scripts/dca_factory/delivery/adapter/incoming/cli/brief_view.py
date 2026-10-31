"""A stage's brief as a person or a stage reads it — Markdown — or as a view takes it — JSON."""

from __future__ import annotations

import typing

from ....domain.service.stage_brief import Brief, written

Model = typing.Dict[str, typing.Any]


def brief_model(brief: Brief) -> Model:
    return dict(
        stage=brief.stage.value, kind=brief.kind.value, about=brief.about.value if brief.about else "",
        said=brief.said.value, common=brief.common.value, own=brief.own.value,
        writes=brief.writes.value if brief.writes else "", window=brief.window.value if brief.window else "",
        told=[dict(rule=t.rule.value, section=t.section.value if t.section else "", words=t.words.value)
              for t in brief.told],
        measured=[dict(rule=m.rule.value, when=m.when.value, refused=m.refused.value if m.refused else "")
                  for m in brief.measured],
        carriers=[dict(role=c.role.value, skill=c.skill.value) for c in brief.carriers])


def markdown(brief: Brief) -> str:
    """The brief in the order a stage works it, all it is told in one text."""
    return written(brief, brief.said).value
