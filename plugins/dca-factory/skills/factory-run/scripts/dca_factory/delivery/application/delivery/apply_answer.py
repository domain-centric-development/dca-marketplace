"""Apply the answer a stage applied: the record says so, the story carries it as an answered line."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.decision_record import RecordId
from ...domain.model.moment import Moment
from ...domain.model.stage import StageName
from ...domain.model.stage_story import Place
from ...domain.model.story import Story
from ..shared.decision_record_repository import DecisionRecordRepository
from ..shared.decision_stamps import DecisionStamps


@dataclasses.dataclass(frozen=True)
class ApplyAnswerCommand:
    story: Story
    record: RecordId
    stage: StageName
    at: Moment


@dataclasses.dataclass(frozen=True)
class AnswerApplied:
    """Applied; `written` the story where the answer became an `answered:` line, None where it was one already."""

    written: typing.Optional[Place]


class ApplyAnswerInputPort(UseCase[ApplyAnswerCommand, AnswerApplied], typing.Protocol):
    """Apply an answered record."""


class ApplyAnswerUseCase(ApplyAnswerInputPort):
    """The record is applied by its aggregate — answered ones only —, saved with its event in one transaction; the
    answer then becomes an `answered:` line of the story."""

    def __init__(self, records: DecisionRecordRepository, stamps: DecisionStamps, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._records = records
        self._stamps = stamps
        self._events = events
        self._transactions = transactions

    def execute(self, command: ApplyAnswerCommand) -> AnswerApplied:
        record = self._records.get(command.record)
        record.apply(command.stage, command.at)

        def save() -> None:
            self._records.save(record)
            self._events.publish_and_clear_events(record)

        self._transactions.in_transaction(save)
        return AnswerApplied(self._stamps.answered_line(command.story, command.record))
