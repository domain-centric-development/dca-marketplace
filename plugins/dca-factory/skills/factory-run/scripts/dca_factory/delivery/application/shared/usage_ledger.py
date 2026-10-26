"""What the stories' journals say they used: per story, the stage invocations the runner journaled and their tokens."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import Store


@dataclasses.dataclass(frozen=True)
class Spent:
    invocations: int
    tokens: int


class UsageLedger(Store, typing.Protocol):
    def stories(self) -> typing.Sequence[str]:
        """Every story with a run or a journal, in id order."""
        ...

    def spent(self, story: str) -> typing.Optional[Spent]:
        """What the story's journal books, None where it has no journal — an in-session run writes none."""
        ...
