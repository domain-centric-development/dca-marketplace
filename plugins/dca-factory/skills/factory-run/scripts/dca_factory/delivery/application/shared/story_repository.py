"""The stories, as the use cases ask for them."""

from __future__ import annotations

import typing

from ....building_blocks import Repository, UseCaseException
from ...domain.model.epic import EpicId
from ...domain.model.story import Story, StoryId


class StoryNotFound(UseCaseException):
    """No story by this id — or not one: two carry it, or it stands in a layout the factory no longer reads. The
    message says which, and where the stories are."""


class StoryRepository(Repository[Story, StoryId], typing.Protocol):
    """The stories under the epics: one story folder each, its state in its front matter."""

    def get(self, story_id: StoryId) -> Story:
        """The story with this id; StoryNotFound otherwise."""
        ...

    def stories_of(self, epic: EpicId) -> typing.Sequence[Story]:
        """Every story of the epic, in the order of its folders."""
        ...
