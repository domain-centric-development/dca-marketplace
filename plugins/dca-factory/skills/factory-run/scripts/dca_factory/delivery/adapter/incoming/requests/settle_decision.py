"""A press on a decision the factory settles itself: an acceptance's yes, a request's own question answered by an
option — the decisions feature's commands."""

from __future__ import annotations

import typing

from ....application.decisions.accept_delivery import AcceptDeliveryCommand, AcceptDeliveryInputPort, Accepted
from ....application.decisions.answer_question import Answered, AnswerQuestionCommand, AnswerQuestionInputPort
from ....application.shared.requests import RequestFacts
from ....domain.model.decision_record import OptionKey, RecordId
from ....domain.model.moment import Moment
from ....domain.model.person import Person
from ....domain.model.story import StoryId


class DecisionSettlement:
    """`accept`: the story's open acceptance takes `answer: accepted` — a yes, nothing to weigh; `answer` naming an
    option and no words: the answer use case writes it where the record is a request's own question."""

    KINDS = ("accept", "answer")

    def __init__(self, accept: AcceptDeliveryInputPort, answer: AnswerQuestionInputPort) -> None:
        self._accept = accept
        self._answer = answer

    def settle(self, request: RequestFacts, at: str) -> typing.Optional[typing.List[str]]:
        by, moment = Person(str(request.get("by", ""))), Moment(at)
        if request["kind"] == "accept":
            accepted = self._accept.execute(AcceptDeliveryCommand(StoryId(request["story"]), by, moment))
            return [accepted.record.value] if isinstance(accepted, Accepted) else None
        if not request.get("option") or request.get("words"):
            return None
        answered = self._answer.execute(AnswerQuestionCommand(RecordId(request["record"]),
                                                              OptionKey(request["option"]), by, moment))
        return [answered.record.value] if isinstance(answered, Answered) else None
