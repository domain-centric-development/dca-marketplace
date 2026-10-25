"""Answer a request's own question with one of its options."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.decision_record import Answer, Asker, DecisionState, Given, OptionKey, RecordId
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


class AnswerQuestionUseCase:
    """An option named for a request's own question (`request:` in the record), open and offering that option, is
    written as the answer; the request that asked runs again and applies it. A stage's question goes through the
    decisions skill, which weighs what an answer changes — a test, the designed map."""

    def __init__(self, records: DecisionRecordRepository) -> None:
        self._records = records

    def execute(self, command: AnswerQuestionCommand) -> AnswerQuestionResult:
        record = self._records.get(command.record)
        if record.asker is not Asker.REQUEST or record.state is not DecisionState.OPEN \
                or command.option not in record.options:
            return NeedsSkill("a stage's question, an answered one, or an option the record does not offer")
        record.answer(Answer(Given(command.option.value), command.by, command.at))
        self._records.save(record)
        return Answered(record.id)
