"""What the gate found over one story, as the rulebook reads it."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.rule import Fired, Refused


class GateFindings(OutputPort, typing.Protocol):
    """A story's gate reports and refusals, through delivery."""

    def fired(self, story: str) -> typing.Tuple[Fired, ...]:
        """Every finding of the latest gate run per stage — none where the story left no report."""
        ...

    def refused(self, story: str) -> typing.Tuple[Refused, ...]:
        """How often the gate refused the story, per name."""
        ...
