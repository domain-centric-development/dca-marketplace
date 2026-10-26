"""The judges' confirmed findings that did not block, still open — a story's and the project's own."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.status_facts import StatusFacts

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ListFindingsQuery:
    pass


class ListFindingsInputPort(UseCase[ListFindingsQuery, Model], typing.Protocol):
    """`rows` (story, where, severity, defect, plain) and the findings file's `name`."""


class ListFindingsUseCase:
    def __init__(self, facts: StatusFacts) -> None:
        self._facts = facts

    def execute(self, query: ListFindingsQuery) -> Model:
        rows = [dict(story=r["owner"], where=r["where"], severity=r["severity"], defect=r["defect"], plain=r["plain"])
                for r in self._facts.finding_records()]
        return dict(rows=rows, name=self._facts.findings_name())
