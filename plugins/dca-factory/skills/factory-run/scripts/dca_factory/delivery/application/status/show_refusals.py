"""Every story's gate refusals, form against substance, the runner's apart from the stages' own — what a bench
counts."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.story import StoryId
from ...domain.model.verdict import FORM_CHECKS, RefusalKind
from ..shared.gate_refusals import GateRefusals

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowRefusalsQuery:
    story: typing.Optional[str] = None


class ShowRefusalsInputPort(UseCase[ShowRefusalsQuery, Model], typing.Protocol):
    """`form_checks` and `stories`: per story `{runner|stages: {form, substance, checks: {check: n}}}`."""


class ShowRefusalsUseCase:
    def __init__(self, refusals: GateRefusals) -> None:
        self._refusals = refusals

    def execute(self, query: ShowRefusalsQuery) -> Model:
        stories = [s for s in self._refusals.stories() if not query.story or s.value == query.story]
        return dict(form_checks=list(FORM_CHECKS), stories={story.value: self._counts(story) for story in stories})

    def _counts(self, story: StoryId) -> Model:
        counts: Model = {}
        for refused in self._refusals.refused(story):
            entry = counts.setdefault(refused.by.value, {"form": 0, "substance": 0, "checks": {}})
            entry[RefusalKind.of(refused.failed).value] += 1
            for check in [c.value for c in refused.failed] or ["unnamed"]:
                entry["checks"][check] = entry["checks"].get(check, 0) + 1
        return counts
