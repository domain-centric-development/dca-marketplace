"""What a story's criteria do to the spec, as a delivery by hand asks it."""

from __future__ import annotations

import dataclasses
import typing

from ...domain.model.story import StoryId


@dataclasses.dataclass(frozen=True)
class SpecChange:
    """Criteria by key and the spec file they stand in."""

    keys: typing.Tuple[str, ...]
    where: str


class StorySpec(typing.Protocol):
    """The spec beside one story's criteria."""

    def changing(self, story: StoryId) -> SpecChange:
        """The criteria the story changes in what holds — none where it only adds."""
        ...

    def take_unproven(self, story: StoryId) -> SpecChange:
        """The story's new criteria merged into the spec, without a test line — the ones taken."""
        ...
