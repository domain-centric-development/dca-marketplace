"""The stories under the epics as the backlog check reads them, each with what keeps it from being read."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from ...domain.model.stage_story import Place, StageStory
from ...domain.model.story import StoryId
from ...domain.model.story_state import Detail, StatusWord


@dataclasses.dataclass(frozen=True)
class BacklogEntry:
    """One story file: the id it carries (else its folder's name) and its folder's name, its status and whether it is
    delivered, and the story — or why its front matter or its criteria cannot be read."""

    label: StoryId
    folder: StoryId
    place: Place
    status: typing.Optional[StatusWord]
    delivered: bool
    story: typing.Optional[StageStory]
    unreadable: typing.Optional[Detail]


class BacklogEntries(OutputPort, typing.Protocol):
    """Every story under the epics."""

    def twice(self) -> typing.Mapping[StoryId, typing.Tuple[Place, ...]]:
        """The ids more than one story carries, lower case, with the files that carry them."""
        ...

    def entries(self) -> typing.Iterable[BacklogEntry]:
        """Every story file, in the order of the files."""
        ...
