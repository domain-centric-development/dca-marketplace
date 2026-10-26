"""Follow the newest output as it is written: each call says what was added since the last — the follower calls it
again and again, and a new output takes over from the one before."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.stage_outputs import Output, StageOutputs


@dataclasses.dataclass(frozen=True)
class FollowOutputQuery:
    story: typing.Optional[str] = None
    process: typing.Optional[str] = None
    request: typing.Optional[str] = None
    current: typing.Optional[Output] = None     # the output followed so far
    offset: int = 0                             # how far it was read
    pending: str = ""                           # an unfinished last line


@dataclasses.dataclass(frozen=True)
class Followed:
    """The output followed now, `started` where it is a new one, the lines added, and where to go on from."""

    current: typing.Optional[Output]
    started: bool
    lines: typing.List[str]
    offset: int
    pending: str


class FollowOutputInputPort(UseCase[FollowOutputQuery, Followed], typing.Protocol):
    """What the newest output added since the last call."""


class FollowOutputUseCase:
    def __init__(self, outputs: StageOutputs) -> None:
        self._outputs = outputs

    def execute(self, query: FollowOutputQuery) -> Followed:
        current, offset, pending, started = query.current, query.offset, query.pending, False
        newest = self._outputs.newest(query.story, query.process, query.request)
        if newest and (current is None or newest.path != current.path):
            current, offset, pending, started = newest, 0, "", True
        if current is None:
            return Followed(None, False, [], 0, "")
        chunk, offset = self._outputs.read(current, offset)
        lines: typing.List[str] = []
        if chunk:
            pending += chunk
            complete, _, pending = pending.rpartition("\n")
            lines = self._outputs.lines(complete)[0]
        return Followed(current, started, lines, offset, pending)
