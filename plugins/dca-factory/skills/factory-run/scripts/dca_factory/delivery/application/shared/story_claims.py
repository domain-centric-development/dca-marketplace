"""The claims other factories hold on stories."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ...domain.model.story import StoryId


@dataclasses.dataclass(frozen=True)
class ClaimHeld:
    """Another factory's claim on a story: who, on which host, since when."""

    who: str
    host: str
    since: str


class Claim(enum.Enum):
    """How a claim went."""

    #: claimed now, or this factory's already
    OWN = "own"
    #: another factory has it
    ELSEWHERE = "elsewhere"
    #: a person has to look — an id collision, or the remote refused for another reason than the race
    NEEDS_PERSON = "needs person"
    #: the profile names no claim remote: nothing claimed, nothing to claim
    NO_REMOTE = "no remote"


@dataclasses.dataclass(frozen=True)
class ClaimOutcome:
    """How the claim went, the other factory's claim where it has the story, and what the claim said on its way."""

    claim: Claim
    held: typing.Optional[ClaimHeld]
    said: typing.Tuple[str, ...]


class StoryClaims(typing.Protocol):
    """The remote's story claims, where the profile names a claim remote."""

    def held_elsewhere(self, story: StoryId) -> typing.Optional[ClaimHeld]:
        """Another factory's claim on the story, fresh from the remote — None where none or no claim remote."""
        ...

    def claim(self, story: StoryId) -> ClaimOutcome:
        """The story claimed on the remote — a claim commit on its main line, its trailers saying who and which."""
        ...

    def release(self, story: StoryId, force: bool) -> int:
        """The story's claim given up by hand — this factory's, or with <force> another's; its exit, said."""
        ...

    def refresh(self) -> int:
        """The remote's claims fetched into the cache the schedule reads, a delivered story's released; its exit."""
        ...

    def free_id(self, prefix: str) -> str:
        """The next `<prefix>-<n>` nobody uses — no local story, none on the remote main line or in its history's
        trailers, no remote claim."""
        ...
