"""The facts of one story that say where it stands: what it says about itself, and what its run left."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story_state import RunFacts, StoryFront


class StoryFacts(OutputPort, typing.Protocol):
    """One story's facts, read where they are kept — its run's only when asked, for a story released to run."""

    def front(self) -> StoryFront:
        """What the story says about itself, and the marks read before its run."""
        ...

    def run(self, front: StoryFront) -> RunFacts:
        """What the story's run left."""
        ...
