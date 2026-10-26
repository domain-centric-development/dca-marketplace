"""What the stories used so far, from their journals — kept per story on disk, so a restart, a second session or a
new run never resets it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.usage_ledger import Spent, UsageLedger


@dataclasses.dataclass(frozen=True)
class ShowSpentQuery:
    """The stories to count — every story with a journal where none is named."""

    stories: typing.Optional[typing.Tuple[str, ...]] = None


@dataclasses.dataclass(frozen=True)
class SpentView:
    by_story: typing.Mapping[str, typing.Optional[Spent]]
    tokens: int


class ShowSpentInputPort(UseCase[ShowSpentQuery, SpentView], typing.Protocol):
    """Per story what its journal books (None without one), and the tokens of all of them."""


class ShowSpentUseCase:
    def __init__(self, ledger: UsageLedger) -> None:
        self._ledger = ledger

    def execute(self, query: ShowSpentQuery) -> SpentView:
        stories = query.stories if query.stories is not None else tuple(self._ledger.stories())
        by_story = {story: self._ledger.spent(story) for story in stories}
        return SpentView(by_story, sum(spent.tokens for spent in by_story.values() if spent))
