"""Follow the factory's own log as it is written (WP-183): the first call says its last lines, each later one what was
added since — the run page's output while nothing else is followed there."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_log import FactoryLog


@dataclasses.dataclass(frozen=True)
class FollowFactoryLogQuery:
    offset: typing.Optional[int] = None         # how far it was read — None: the first call
    pending: str = ""                           # an unfinished last line
    tail: int = 200                             # how many of its last lines the first call says


@dataclasses.dataclass(frozen=True)
class LogFollowed:
    """Whether there is a log, the lines added, and where to go on from."""

    written: bool
    lines: typing.List[str]
    offset: int
    pending: str


class FollowFactoryLogInputPort(UseCase[FollowFactoryLogQuery, LogFollowed], typing.Protocol):
    """What the factory's log added since the last call."""


class FollowFactoryLogUseCase:
    """A log that shrank was kept aside and a new one begun: it is read again from its start. Only whole lines are
    said; the rest waits for its line break."""

    def __init__(self, log: FactoryLog) -> None:
        self._log = log

    def execute(self, query: FollowFactoryLogQuery) -> LogFollowed:
        size = self._log.size()
        if size is None:
            return LogFollowed(False, [], 0, "")
        if query.offset is None:
            text, offset = self._log.read(0)
            return LogFollowed(True, text.splitlines()[-query.tail:], offset, "")
        offset, pending = (0, "") if size < query.offset else (query.offset, query.pending)
        if size == offset:
            return LogFollowed(True, [], offset, pending)
        chunk, offset = self._log.read(offset)
        *whole, pending = (pending + chunk).split("\n")
        return LogFollowed(True, [line.rstrip("\r") for line in whole], offset, pending)
