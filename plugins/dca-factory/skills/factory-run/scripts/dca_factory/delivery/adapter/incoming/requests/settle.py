"""A request the factory settles itself, without a tool: where the person's press is the whole decision and the
files say everything it implies."""

from __future__ import annotations

import typing

from ....application.backlog.release_stories import (
    Released, ReleaseStoriesCommand, ReleaseStoriesInputPort)
from ....application.decisions.accept_delivery import AcceptDeliveryCommand, AcceptDeliveryInputPort, Accepted
from ....application.decisions.answer_question import Answered, AnswerQuestionCommand, AnswerQuestionInputPort
from ....application.shared.requests import Request
from ....domain.model.decision_record import OptionKey, RecordId
from ....domain.model.epic import EpicId
from ....domain.model.moment import Moment
from ....domain.model.person import Person
from ....domain.model.story import StoryId


class Settlement:
    """Which press needs no judgement, translated into its use case's command:

    - `accept`: the story's open acceptance takes `answer: accepted` — a yes, nothing to weigh;
    - `answer` naming an option and no words: the answer use case writes it where the record is a request's own
      question; a stage's question goes through the decisions skill;
    - `release`: the release use case approves the drafts whose question pass ran on them as they stand.

    Every other kind is a skill's."""

    def __init__(self, accept: AcceptDeliveryInputPort, answer: AnswerQuestionInputPort,
                 release: ReleaseStoriesInputPort) -> None:
        self._accept = accept
        self._answer = answer
        self._release = release

    def settle(self, request: Request, at: str) -> typing.Optional[typing.List[str]]:
        """The ids of what it wrote — records, stories — or None where a skill must work it."""
        by, moment = Person(str(request.get("by", ""))), Moment(at)
        if request["kind"] == "accept":
            accepted = self._accept.execute(AcceptDeliveryCommand(StoryId(request["story"]), by, moment))
            return [accepted.record.value] if isinstance(accepted, Accepted) else None
        if request["kind"] == "answer":
            if not request.get("option") or request.get("words"):
                return None
            answered = self._answer.execute(AnswerQuestionCommand(RecordId(request["record"]),
                                                                  OptionKey(request["option"]), by, moment))
            return [answered.record.value] if isinstance(answered, Answered) else None
        if request["kind"] == "release":
            epic = request.get("epic")
            released = self._release.execute(ReleaseStoriesCommand(
                tuple(StoryId(s) for s in str(request.get("story", "")).split()),
                EpicId(epic) if epic else None, str(request["id"]), by, moment))
            return [story.value for story in released.stories] if isinstance(released, Released) else None
        return None
