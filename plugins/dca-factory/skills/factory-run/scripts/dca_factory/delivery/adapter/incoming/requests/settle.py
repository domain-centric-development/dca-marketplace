"""A request the factory settles itself, without a tool: where the person's press is the whole decision and the
files say everything it implies. Each feature settles its own kinds (`settle_decision`, `settle_release`); every
other kind is a skill's."""

from __future__ import annotations

import typing

from ....application.backlog.release_stories import ReleaseStoriesInputPort
from ....application.decisions.accept_delivery import AcceptDeliveryInputPort
from ....application.decisions.answer_question import AnswerQuestionInputPort
from ....application.shared.requests import RequestFacts
from .settle_decision import DecisionSettlement
from .settle_release import ReleaseSettlement


class Settlement:
    """Which press needs no judgement, handed to the feature that settles it."""

    def __init__(self, accept: AcceptDeliveryInputPort, answer: AnswerQuestionInputPort,
                 release: ReleaseStoriesInputPort) -> None:
        self._features = (DecisionSettlement(accept, answer), ReleaseSettlement(release))

    def settle(self, request: RequestFacts, at: str) -> typing.Optional[typing.List[str]]:
        """The ids of what it wrote — records, stories — or None where a skill must work it."""
        for feature in self._features:
            if request["kind"] in feature.KINDS:
                return feature.settle(request, at)
        return None
