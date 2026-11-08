"""The facts of one story that say where it stands: what it says about itself, and what its run left."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.decision_record import DecisionRecord
from ...domain.model.story import Story
from ...domain.model.story_state import RunFacts, StoryMarks


class StoryFacts(OutputPort, typing.Protocol):
    """One story's facts, read where they are kept — its run's only when asked, for a story released to run."""

    def story(self) -> Story:
        """The story, as its file says it."""
        ...

    def story_marks(self) -> StoryMarks:
        """The marks read before its run: a stage changed it, it is published, another factory claims it."""
        ...

    def records(self, story: Story) -> typing.Sequence[DecisionRecord]:
        """The story's decision records — none where they cannot be read (`run` says why)."""
        ...

    def run(self, story: Story) -> RunFacts:
        """What the story's run left."""
        ...
