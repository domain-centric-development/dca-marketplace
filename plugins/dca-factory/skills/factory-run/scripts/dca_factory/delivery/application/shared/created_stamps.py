"""The `created:` line of the stories and epics, as a backfill asks for it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from ...domain.model.moment import Moment


@dataclasses.dataclass(frozen=True)
class Unstamped:
    """A story's or an epic's file without a `created:` line."""

    path: str
    #: "story" or "epic"
    kind: str


class CreatedStamps(OutputPort, typing.Protocol):
    """The backlog's files and when each came to be."""

    def unstamped(self) -> typing.Sequence[Unstamped]:
        """Every story and epic without a `created:` line — a line of any content is the person's, a file that
        cannot be read is the gate's to name."""
        ...

    def first_added(self, path: str) -> typing.Optional[Moment]:
        """When the version history first added the file, through its renames — None where it holds none."""
        ...

    def file_time(self, path: str) -> Moment:
        """The file's own modification time."""
        ...

    def stamp(self, path: str, created: Moment) -> None:
        """`created:` written into the file's front matter."""
        ...
