"""What became of a proposal — asked of delivery, in delivery's terms."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class Backlog(OutputPort, typing.Protocol):
    """Delivery's backlog, as far as discovery may ask it."""

    def epic_of(self, proposal: str) -> str:
        """The epic that holds the proposal, '' where none does yet."""
        ...
