"""Write the lessons: each candidate nobody was asked yet becomes an open lesson record in decide."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.moment import Moment
from ..shared.lesson_records import LessonProposals, LessonRecords
from ..shared.lesson_signals import LessonSignals

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class WriteLessonsCommand:
    at: Moment


class WriteLessonsInputPort(UseCase[WriteLessonsCommand, Model], typing.Protocol):
    """`written`: [{id, kind, path}] of the records written now — none where nothing new reached its threshold."""


class WriteLessonsUseCase(WriteLessonsInputPort):
    def __init__(self, signals: LessonSignals, records: LessonRecords) -> None:
        self._proposals = LessonProposals(signals, records)

    def execute(self, command: WriteLessonsCommand) -> Model:
        return dict(written=[dict(id=rid, kind=kind.value, path=path)
                             for rid, kind, path in self._proposals.propose(command.at)])
