"""The discovery reports, as the use cases read them."""

from __future__ import annotations

import typing

from ....building_blocks import Store
from ...domain.model.report import Report, Topic


class ReportStore(Store, typing.Protocol):
    """The reports under the project's discovery folder: one per topic, with the material it cites beside it."""

    def where(self) -> str:
        """The discovery folder, as a person reads it."""
        ...

    def topics(self) -> typing.List[Topic]:
        """Every topic that has a report, by name."""
        ...

    def report_path(self, topic: Topic) -> str:
        """The topic's report as a project path."""
        ...

    def read(self, topic: Topic) -> typing.Optional[Report]:
        """The topic's report — None where it has none."""
        ...

    def title(self, topic: Topic) -> str:
        """The report's title, the topic's name where it has none."""
        ...

    def resolves(self, topic: Topic, path: str) -> bool:
        """Whether a path a source names is there — beside the report or in the project."""
        ...

    def ignores_originals(self, topic: Topic) -> bool:
        """Whether the topic's handed-over originals stay out of git."""
        ...
