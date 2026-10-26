"""The gates' refusals a story's journal holds — the runner's and the stages' own, each with the checks it named."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import Store
from ...domain.model.story import StoryId
from ...domain.model.verdict import CheckName


class RefusedBy(enum.Enum):
    """Whose gate run refused: the runner's (the one that decides) or a stage's own check of its work."""

    RUNNER = "runner"
    STAGES = "stages"


@dataclasses.dataclass(frozen=True)
class Refused:
    by: RefusedBy
    failed: typing.Tuple[CheckName, ...]


class GateRefusals(Store, typing.Protocol):
    def stories(self) -> typing.Sequence[StoryId]:
        """Every story with a run, in id order."""
        ...

    def refused(self, story: StoryId) -> typing.Sequence[Refused]:
        """The story's refused gate runs, in the journal's order."""
        ...
