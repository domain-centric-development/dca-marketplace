"""What a stage changed of the person's own: the story and its answers."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story import StoryId


class OwnedChanges(OutputPort, typing.Protocol):
    """The mark a stage leaves where it changed the story or an answer, and what it names."""

    def changed(self, story: StoryId) -> typing.Sequence[str]:
        """The parts the mark names as changed — none without a mark."""
        ...

    def clear(self, story: StoryId) -> None:
        """The mark removed."""
        ...
