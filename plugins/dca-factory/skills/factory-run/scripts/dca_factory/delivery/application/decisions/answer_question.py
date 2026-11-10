"""Answer a request's own question with one of its options."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.decision_record import NotOpen, OptionKey, OptionNotOffered, RecordId
from ...domain.model.moment import Moment
from ...domain.model.person import Person
from ..shared.decision_record_repository import DecisionRecordRepository
from ..shared.outcomes import NeedsSkill


@dataclasses.dataclass(frozen=True)
class AnswerQuestionCommand:
    record: RecordId
    option: OptionKey
    by: Person
    at: Moment


@dataclasses.dataclass(frozen=True)
class Answered:
    record: RecordId


AnswerQuestionResult = typing.Union[Answered, NeedsSkill]


class AnswerQuestionInputPort(UseCase[AnswerQuestionCommand, AnswerQuestionResult], typing.Protocol):
    """Answer a question with an option, where the option is the whole decision."""


class AnswerQuestionUseCase(AnswerQuestionInputPort):
    """An option named for a request's own question (`request:` in the record), open and offering that option, is
    written as the answer; the request that asked runs again and applies it. So is a lesson's `not now` or `never`,
    which writes nothing else. A stage's question goes through the decisions skill, which weighs what an answer
    changes — a test, the designed map —, and so does a lesson's place, which the skill owning it writes."""

    def __init__(self, records: DecisionRecordRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._events = events
        self._transactions = transactions
        self._records = records

    def execute(self, command: AnswerQuestionCommand) -> AnswerQuestionResult:
        record = self._records.get(command.record)
        if not record.settles_alone(command.option):
            return NeedsSkill("a stage's question or a lesson's place — the decisions skill weighs what its answer "
                              "changes and has the owning skill write it")
        try:
            record.choose(command.option, command.by, command.at)
        except (NotOpen, OptionNotOffered) as refused:
            return NeedsSkill(str(refused))

        def save() -> None:
            self._records.save(record)
            self._events.publish_and_clear_events(record)

        self._transactions.in_transaction(save)
        return Answered(record.id)
