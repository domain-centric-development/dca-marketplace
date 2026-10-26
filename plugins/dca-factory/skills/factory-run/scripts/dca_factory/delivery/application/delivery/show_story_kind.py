"""What a story is — story, journey, task, adoption: the stages it runs."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.stage import StoryKind
from ...domain.model.story import StoryId
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class ShowStoryKindQuery:
    story: StoryId


class ShowStoryKindInputPort(UseCase[ShowStoryKindQuery, StoryKind], typing.Protocol):
    """The story's kind; StoryNotFound where no single story has the id."""


class ShowStoryKindUseCase:
    def __init__(self, stories: StoryRepository) -> None:
        self._stories = stories

    def execute(self, query: ShowStoryKindQuery) -> StoryKind:
        return self._stories.get(query.story).kind
