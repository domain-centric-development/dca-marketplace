"""What discovery proposes — asked across the boundary, in discovery's terms."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class DiscoveryReports(OutputPort, typing.Protocol):
    """The discovery reports of the project: one per topic, its proposed work by name."""

    def report_of(self, topic: str) -> typing.Optional[str]:
        """The topic's report, as a project path — None where the topic has none."""
        ...

    def proposals_in(self, report: str) -> typing.List[str]:
        """The names of the work the report proposes, in its order."""
        ...
