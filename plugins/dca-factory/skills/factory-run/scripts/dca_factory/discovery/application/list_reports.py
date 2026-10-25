"""List the discovery reports: each topic, the work it proposes and what became of it, its description changes."""

from __future__ import annotations

import dataclasses
import typing

from ...building_blocks import UseCase
from ..domain.model.report import Text
from .shared.backlog import Backlog
from .shared.report_store import ReportStore

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ListReportsQuery:
    pass


class ListReportsInputPort(UseCase[ListReportsQuery, Model], typing.Protocol):
    """The discovery reports."""


class ListReportsUseCase:
    """Every topic with its proposed epics — and the epic of the backlog that holds each, as delivery says — and its
    proposed description changes; what the report says, read the way the check reads it."""

    def __init__(self, reports: ReportStore, backlog: Backlog) -> None:
        self._reports = reports
        self._backlog = backlog

    def execute(self, query: ListReportsQuery) -> Model:
        topics = []
        for topic in self._reports.topics():
            report = self._reports.read(topic)
            if report is None:
                continue
            proposals = [dict(id=item.name.value,
                              **{k: item.field(Text(k)).value for k in ("intent", "goal", "metric", "domain_contact")},
                              epic=self._backlog.epic_of(item.name.value))
                         for item in report.proposals]
            changes = [dict(target=item.name.value, change=item.field(Text("change")).value,
                            why=item.field(Text("why")).value) for item in report.changes]
            topics.append(dict(topic=topic.value, report=self._reports.report_path(topic),
                               title=self._reports.title(topic), proposals=proposals, description_changes=changes))
        return dict(store=self._reports.where() + "/", topics=topics)
