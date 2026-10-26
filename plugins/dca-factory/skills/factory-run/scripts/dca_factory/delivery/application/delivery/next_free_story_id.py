"""The next story id nobody uses, for a new story: a delivered story's id never comes free again."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.story_claims import StoryClaims


@dataclasses.dataclass(frozen=True)
class NextFreeStoryIdQuery:
    prefix: str


class NextFreeStoryIdInputPort(UseCase[NextFreeStoryIdQuery, str], typing.Protocol):
    """The id."""


class NextFreeStoryIdUseCase:
    def __init__(self, claims: StoryClaims) -> None:
        self._claims = claims

    def execute(self, command: NextFreeStoryIdQuery) -> str:
        return self._claims.free_id(command.prefix)
