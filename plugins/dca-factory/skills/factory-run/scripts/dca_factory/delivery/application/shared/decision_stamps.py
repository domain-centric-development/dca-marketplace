"""An answer applied: its record stamped, the story given its `answered:` line."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story import Story
from ...domain.model.stage_story import Place
from ...domain.service.decision_checks import Applying


class DecisionStamps(OutputPort, typing.Protocol):
    """The records and the story, written where an answer was applied."""

    def apply(self, story: Story, applying: Applying) -> typing.Optional[Place]:
        """The record stamped applied by its stage, the answer an `answered:` line of the story — the story's place
        where the line was written, None where the story has it already."""
        ...
