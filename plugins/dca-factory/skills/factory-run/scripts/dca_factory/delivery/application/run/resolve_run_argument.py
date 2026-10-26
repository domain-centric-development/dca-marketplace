"""Resolve `/factory-run <argument>`: the backlog, one story, a wish — or an id no story has, named with the ids the
backlog has."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.run_argument import ArgumentMeaning, RunArgument
from ...domain.model.story import StoryId
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class ResolveRunArgumentQuery:
    argument: str


@dataclasses.dataclass(frozen=True)
class ResolvedArgument:
    """What the argument means; the story it names, where it names one; the backlog's ids, where it names none."""

    meaning: ArgumentMeaning
    story: typing.Optional[StoryId] = None
    word: str = ""
    known: typing.Tuple[StoryId, ...] = ()


class ResolveRunArgumentInputPort(UseCase[ResolveRunArgumentQuery, ResolvedArgument], typing.Protocol):
    """The argument's meaning."""


class ResolveRunArgumentUseCase:
    def __init__(self, stories: StoryRepository) -> None:
        self._stories = stories

    def execute(self, query: ResolveRunArgumentQuery) -> ResolvedArgument:
        argument = RunArgument(query.argument)
        word = argument.single_word()
        named = self._named(word.value) if word else None
        meaning = argument.meaning(named)
        if meaning is ArgumentMeaning.UNKNOWN and word:
            return ResolvedArgument(meaning, word=word.value, known=tuple(self._stories.ids()))
        return ResolvedArgument(meaning, story=named)

    def _named(self, word: str) -> typing.Optional[StoryId]:
        try:
            story = self._stories.find_by_id(StoryId(word))
        except ValueError:
            return None
        return story.id if story else None
