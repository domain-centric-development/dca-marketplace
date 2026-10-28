"""The reports of every implementation of one scenario contract, as a parity config names them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.stage_story import ParityFacts


class ParityReports(OutputPort, typing.Protocol):
    """The parity configs of a project."""

    def facts(self, config: str) -> ParityFacts:
        """The config's scenario contract and each implementation's reports."""
        ...
