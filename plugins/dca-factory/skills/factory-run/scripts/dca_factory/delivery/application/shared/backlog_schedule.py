"""The schedule as a backlog run reads it before every story: what runs next, and whether anything waits on an
answer."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort


@dataclasses.dataclass(frozen=True)
class ScheduleRead:
    """The schedule read once: as a person reads it, the stories it names next with the stage each starts from, and
    whether a story waits on an answer that would change it. Not `readable`: `text` says why."""

    readable: bool
    text: str
    following: typing.Tuple[typing.Tuple[str, str], ...] = ()
    waits: bool = False


class BacklogSchedule(OutputPort, typing.Protocol):
    """The schedule of the checkout, read off its files every time."""

    def read(self, slots: int, busy: typing.Sequence[str], skip: typing.Sequence[str]) -> ScheduleRead:
        """The schedule for <slots> free slots, the stories in <busy> running, those in <skip> set aside."""
        ...
