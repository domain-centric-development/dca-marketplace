"""Check that story and spec agree: every criterion of a delivered story that is still there stands in its spec."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.delivered_specs import DeliveredSpecs


@dataclasses.dataclass(frozen=True)
class CheckSpecQuery:
    pass


@dataclasses.dataclass(frozen=True)
class SpecChecked:
    """The disagreements, one line each, and how many delivered stories were looked at."""

    problems: typing.List[str]
    delivered: int


class CheckSpecInputPort(UseCase[CheckSpecQuery, SpecChecked], typing.Protocol):
    """Check story against spec."""


class CheckSpecUseCase:
    """In one direction: a delivered criterion missing from its spec disagrees — unless a story delivered at the same
    time or later removed it by its plan. Whether a scenario came from a story is not asked: a delivered story may be
    gone. Then the shape of every context's spec, as a delivery checks it before it writes."""

    def __init__(self, specs: DeliveredSpecs) -> None:
        self._specs = specs

    def execute(self, query: CheckSpecQuery) -> SpecChecked:
        delivered = self._specs.delivered()
        removed: typing.Dict[typing.Tuple[str, str], typing.List[str]] = {}
        for story in delivered:
            for key in story.removes:
                removed.setdefault((story.place, key), []).append(story.when)
        problems = []
        for story in sorted(delivered, key=lambda s: (s.when, s.story)):
            for key in story.keys:
                later = [when for when in removed.get((story.place, key), []) if when >= story.when]
                if key not in story.held and not later:
                    problems.append(f"{story.story}: `{key}` is delivered and not in {story.target}")
        return SpecChecked(problems + self._specs.shapes(), len(delivered))
