"""A press that releases drafts the factory may release itself — the backlog feature's command."""

from __future__ import annotations

import typing

from ....application.backlog.release_stories import Released, ReleaseStoriesCommand, ReleaseStoriesInputPort
from ....application.shared.outcomes import NeedsSkill
from ....application.shared.requests import RequestFacts
from ....domain.model.epic import EpicId
from ....domain.model.moment import Moment
from ....domain.model.person import Person
from ....domain.model.story import StoryId


class ReleaseSettlement:
    """`release`: the release use case approves the drafts whose question pass ran on them as they stand."""

    KINDS = ("release",)

    def __init__(self, release: ReleaseStoriesInputPort) -> None:
        self._release = release

    def settle(self, request: RequestFacts, at: str) -> typing.Optional[typing.List[str]]:
        epic = request.get("epic")
        released = self._release.execute(ReleaseStoriesCommand(
            tuple(StoryId(s) for s in str(request.get("story", "")).split()),
            EpicId(epic) if epic else None, str(request["id"]), Person(str(request.get("by", ""))), Moment(at)))
        match released:
            case Released():
                return [story.value for story in released.stories]
            case NeedsSkill():
                return None
            case _:
                typing.assert_never(released)
