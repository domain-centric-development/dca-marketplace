"""Delivery's backlog, asked through delivery's open host service — never through its files."""

from __future__ import annotations

from .....delivery.api import epic_of_proposal
from ....application.shared.backlog import Backlog


class DeliveryBacklog(Backlog):
    """What became of a proposal, in the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def epic_of(self, proposal: str) -> str:
        return epic_of_proposal(self._cwd, proposal)
