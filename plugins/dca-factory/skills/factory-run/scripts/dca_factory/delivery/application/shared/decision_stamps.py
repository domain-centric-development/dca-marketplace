"""An answer applied: the story given its `answered:` line — the record itself is applied by its aggregate."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.decision_record import RecordId
from ...domain.model.story import Story
from ...domain.model.stage_story import Place


class DecisionStamps(OutputPort, typing.Protocol):
    """The story, written where an answer was applied."""

    def answered_line(self, story: Story, record: RecordId) -> typing.Optional[Place]:
        """The record's answer an `answered:` line of the story — the story's place where the line was written, None
        where the story has it already or the record is gone."""
        ...
