"""A story published as its branch (several factories, one backlog): what its delivery changed there, taken back."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from ...domain.model.story import StoryId, StoryStatus
from .story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class TakenBack:
    """The spec files set back as the remote main line has them, and that main line by its name."""

    spec_files: typing.Tuple[str, ...]
    main: str


class PublishedBranches(OutputPort, typing.Protocol):
    def published(self, story: StoryId) -> bool:
        """The story has a published branch in this checkout."""
        ...

    def set_back_spec(self, story: StoryId) -> TakenBack:
        """The spec's scenarios and journeys on the story's branch as the remote main line has them."""
        ...

    def published_over(self, story: StoryId) -> StoryStatus:
        """The status the story was published over — approved where nothing was kept."""
        ...

    def stories(self, story: StoryId) -> StoryRepository:
        """The stories as the story's branch has them, in its own checkout."""
        ...

    def commit_taken_back(self, story: StoryId, taken: TakenBack) -> None:
        """The branch back to before its delivery, committed; its published mark gone."""
        ...
