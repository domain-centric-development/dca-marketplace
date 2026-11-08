"""Accept a delivered story that waits for a person's look."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.decision_record import RecordId
from ...domain.model.moment import Moment
from ...domain.model.person import Person
from ...domain.model.story import StoryId
from ..shared.decision_record_repository import DecisionRecordRepository
from ..shared.outcomes import NeedsSkill
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class AcceptDeliveryCommand:
    story: StoryId
    by: Person
    at: Moment


@dataclasses.dataclass(frozen=True)
class Accepted:
    record: RecordId


AcceptDeliveryResult = typing.Union[Accepted, NeedsSkill]


class AcceptDeliveryInputPort(UseCase[AcceptDeliveryCommand, AcceptDeliveryResult], typing.Protocol):
    """Accept a delivery — a yes, nothing to weigh."""


class AcceptDeliveryUseCase(AcceptDeliveryInputPort):
    """The story's open acceptance takes `answer: accepted`."""

    def __init__(self, stories: StoryRepository, records: DecisionRecordRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._events = events
        self._transactions = transactions
        self._stories = stories
        self._records = records

    def execute(self, command: AcceptDeliveryCommand) -> AcceptDeliveryResult:
        self._stories.get(command.story)
        record = self._records.open_acceptance_of(command.story)
        if record is None:
            return NeedsSkill("the story waits for no acceptance")
        record.accept(command.by, command.at)

        def save() -> None:
            self._records.save(record)
            self._events.publish_and_clear_events(record)

        self._transactions.in_transaction(save)
        return Accepted(record.id)
