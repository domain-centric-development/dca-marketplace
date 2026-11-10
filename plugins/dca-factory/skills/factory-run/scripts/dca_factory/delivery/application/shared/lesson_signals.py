"""The signals a lesson is counted from, and the lessons already asked — read from the project's files."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.lesson import Decided, Signal


class LessonSignals(OutputPort, typing.Protocol):
    """What repeats across the stories, and what a person already said about it."""

    def signals(self) -> typing.Sequence[Signal]:
        """Every counted occurrence: a stage's tagged question, a judge's finding with a rule, a code or a term, a
        coded correction at acceptance, an answered assumption, a flagged term — each with the story and the record,
        row or line it stands in."""
        ...

    def decided(self) -> typing.Sequence[Decided]:
        """Every lesson record: its kind and key, the place its answer named (None while it waits), and the stories
        its evidence held when it was asked."""
        ...
