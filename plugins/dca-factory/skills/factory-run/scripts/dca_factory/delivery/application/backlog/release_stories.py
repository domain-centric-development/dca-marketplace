"""Release drafts — stories by id, or every draft of an epic — where the factory may do it without a skill."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.epic import EpicId
from ...domain.model.moment import Moment
from ...domain.model.person import Person
from ...domain.model.story import Assumption, Story, StoryId, StoryStatus
from ..shared.decision_record_repository import DecisionRecordRepository
from ..shared.outcomes import NeedsSkill
from ..shared.story_journal import StoryJournal
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class ReleaseStoriesCommand:
    """The stories by id — or, with `epic`, every draft of that epic — released on a person's request."""

    stories: typing.Tuple[StoryId, ...]
    epic: typing.Optional[EpicId]
    request: str
    by: Person
    at: Moment


@dataclasses.dataclass(frozen=True)
class Released:
    stories: typing.Tuple[StoryId, ...]


ReleaseStoriesResult = typing.Union[Released, NeedsSkill]


class ReleaseStoriesInputPort(UseCase[ReleaseStoriesCommand, ReleaseStoriesResult], typing.Protocol):
    """Release drafts the factory may release itself."""


class ReleaseStoriesUseCase:
    """A draft whose question pass ran on it as it stands and that no open record holds is approved, its release an
    answered assumption — of an epic, only where every draft is such a one. Anything else needs the backlog skill,
    which asks what the drafts leave open."""

    def __init__(self, stories: StoryRepository, records: DecisionRecordRepository, journal: StoryJournal) -> None:
        self._stories = stories
        self._records = records
        self._journal = journal

    def execute(self, command: ReleaseStoriesCommand) -> ReleaseStoriesResult:
        drafts: typing.List[Story]
        if command.epic is not None:
            drafts = [s for s in self._stories.stories_of(command.epic) if s.status is StoryStatus.DRAFT]
        else:
            drafts = [self._stories.get(story_id) for story_id in command.stories]
        if not drafts or not all(self._releasable(story) for story in drafts):
            return NeedsSkill("a draft whose question pass did not run on it as it stands, or a record holds it")
        answered = Assumption(f"- answered: the story is released for building (request {command.request}, "
                              f"{command.by.value}, {command.at.value}).")
        for story in drafts:
            story.release(answered)
            self._stories.save(story)
        return Released(tuple(story.id for story in drafts))

    def _releasable(self, story: Story) -> bool:
        return story.status is StoryStatus.DRAFT and self._journal.question_pass_ran(story.id) \
            and not self._records.open_records_of(story.id)
