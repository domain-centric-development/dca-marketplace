"""Ask a person to accept a story every gate passed, before it counts as delivered."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.decision_record import DecisionRecord, RecordId
from ...domain.model.moment import Moment
from ...domain.model.story import StoryId
from ..shared.decision_record_repository import DecisionRecordRepository


@dataclasses.dataclass(frozen=True)
class AskAcceptanceCommand:
    story: StoryId
    at: Moment


@dataclasses.dataclass(frozen=True)
class AcceptanceAskedFor:
    """The record that asks."""

    record: RecordId


class AskAcceptanceInputPort(UseCase[AskAcceptanceCommand, AcceptanceAskedFor], typing.Protocol):
    """Ask for an acceptance."""


class AskAcceptanceUseCase(AskAcceptanceInputPort):
    """The story's next acceptance record, made by the aggregate and saved with its event in one transaction."""

    def __init__(self, records: DecisionRecordRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._records = records
        self._events = events
        self._transactions = transactions

    def execute(self, command: AskAcceptanceCommand) -> AcceptanceAskedFor:
        record = DecisionRecord.ask_acceptance(self._records.next_acceptance_id(command.story), command.story,
                                               command.at)

        def save() -> None:
            self._records.save(record)
            self._events.publish_and_clear_events(record)

        self._transactions.in_transaction(save)
        return AcceptanceAskedFor(record.id)
