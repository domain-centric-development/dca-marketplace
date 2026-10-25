"""The claims other factories hold on stories."""

from __future__ import annotations

import dataclasses
import typing

from ...domain.model.story import StoryId


@dataclasses.dataclass(frozen=True)
class ClaimHeld:
    """Another factory's claim on a story: who, on which host, since when."""

    who: str
    host: str
    since: str


class StoryClaims(typing.Protocol):
    """The remote's story claims, where the profile names a claim remote."""

    def held_elsewhere(self, story: StoryId) -> typing.Optional[ClaimHeld]:
        """Another factory's claim on the story, fresh from the remote — None where none or no claim remote."""
        ...
