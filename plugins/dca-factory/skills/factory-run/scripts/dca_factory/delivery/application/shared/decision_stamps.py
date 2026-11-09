"""An answer applied: the line the gate wrote into the story is its own."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story_words import Place
from ...domain.model.story import StoryId


class DecisionStamps(OutputPort, typing.Protocol):
    """The story's marks, where the gate wrote an answer into it."""

    def regard(self, story: StoryId) -> Place:
        """The answered line the gate wrote is its own — the story as planned takes it, so it does not read as the
        story changed after it was planned —; where the story is."""
        ...
