"""A story's stage figures from its journal alone — for a journal whose story is no longer in the backlog."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.status_facts import StatusFacts

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowJournalStoryQuery:
    story: str


class ShowJournalStoryInputPort(UseCase[ShowJournalStoryQuery, Model], typing.Protocol):
    """`stages`, the `models` they ran on, the stages whose requested model was `not_applied`, and `priced`."""


class ShowJournalStoryUseCase:
    def __init__(self, facts: StatusFacts) -> None:
        self._facts = facts

    def execute(self, query: ShowJournalStoryQuery) -> Model:
        facts = self._facts.story_facts(query.story, None)
        stages = facts["stages"]
        return dict(stages=stages, models=sorted({m for e in stages.values() for m in e["models"]}),
                    not_applied=sorted({r for e in stages.values() if e["not_applied"] for r in e["requested"]}),
                    priced=facts["priced"] > 0)
