"""Give a story's claim on the remote up by hand: its remote branch deleted — this factory's claim, or with force another's."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.story import StoryId
from ..shared.story_claims import StoryClaims


@dataclasses.dataclass(frozen=True)
class ReleaseStoryClaimCommand:
    story: StoryId
    force: bool = False


class ReleaseStoryClaimInputPort(UseCase[ReleaseStoryClaimCommand, int], typing.Protocol):
    """Its exit."""


class ReleaseStoryClaimUseCase:
    def __init__(self, claims: StoryClaims) -> None:
        self._claims = claims

    def execute(self, command: ReleaseStoryClaimCommand) -> int:
        return self._claims.release(command.story, command.force)
