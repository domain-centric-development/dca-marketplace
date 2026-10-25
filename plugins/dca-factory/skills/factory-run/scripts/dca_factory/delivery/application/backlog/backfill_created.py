"""`created:` into every story and epic that has none."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.created_stamps import CreatedStamps


@dataclasses.dataclass(frozen=True)
class BackfillCreatedCommand:
    """Every unstamped story and epic, once."""


@dataclasses.dataclass(frozen=True)
class Backfilled:
    stories: int
    epics: int
    #: how many took the file's own time, the history holding none
    from_file: int


class BackfillCreatedInputPort(UseCase[BackfillCreatedCommand, Backfilled], typing.Protocol):
    """Backfill `created:`."""


class BackfillCreatedUseCase:
    """Idempotent and never over a value there. The time is when the history first added the file, followed through
    its renames — a file a layout change moved keeps its first day; a file the history does not hold yet takes its
    own modification time."""

    def __init__(self, stamps: CreatedStamps) -> None:
        self._stamps = stamps

    def execute(self, command: BackfillCreatedCommand) -> Backfilled:
        written = {"story": 0, "epic": 0}
        from_file = 0
        for unstamped in self._stamps.unstamped():
            created = self._stamps.first_added(unstamped.path)
            if created is None:
                created, from_file = self._stamps.file_time(unstamped.path), from_file + 1
            self._stamps.stamp(unstamped.path, created)
            written[unstamped.kind] += 1
        return Backfilled(written["story"], written["epic"], from_file)
