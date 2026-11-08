"""The project's story journals, as the rulebook reads them: the lines a reading of the refusals and of a story's route
needs."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.runs import StoryJournal


class ProjectJournals(OutputPort, typing.Protocol):
    """Every story of the project that left a journal, through delivery."""

    def journals(self) -> typing.Tuple[StoryJournal, ...]:
        """Each story's journal, its route's lines in order — none where the project has no journal."""
        ...
