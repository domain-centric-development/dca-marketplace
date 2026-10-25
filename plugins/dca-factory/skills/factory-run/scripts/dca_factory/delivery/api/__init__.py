"""Delivery's open host service: what another context may ask delivery, in delivery's published terms."""

from __future__ import annotations

import os

from ...sharedkernel.adapter.outgoing.profile.profile_files import place
from ..adapter.outgoing.files.epic_files import epic_holding


def epic_of_proposal(cwd: str, proposal: str) -> str:
    """The epic of the backlog that holds a proposal of discovery — '' where none does yet."""
    return epic_holding(os.path.join(cwd, place("epics")), proposal)
