"""The open stories, asked through delivery's open host service and read into the spec's model."""

from __future__ import annotations

import typing

from .....delivery.api import open_stories
from ....domain.model.context_spec import ContextName, OpenStory, Statement, StoryRef
from ..files.context_spec_files import criterion_of
from ..files.spec_files import context_folder
from ....api.published import story_entries
from ....application.shared.open_stories import OpenStories


class OpenStoryFiles(OpenStories):
    """The stories of the project <cwd> not delivered yet, each with the criteria of its story file."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def not_delivered(self) -> typing.Sequence[OpenStory]:
        return [OpenStory(StoryRef(found["id"]), Statement(found["title"]), Statement(found["status"]),
                          ContextName(context_folder(found["context"])),
                          tuple(criterion_of(item, "") for item in story_entries(found["body"])))
                for found in open_stories(self._cwd)]
