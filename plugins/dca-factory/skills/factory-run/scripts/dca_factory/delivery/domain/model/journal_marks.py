"""What a story's journal says about its hand-overs, by the events' order alone (WP-94): which file was written, which
gate passed, held or refused, which file was marked an earlier pass's — each by the number of its latest event."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value


class MarkKind(enum.Enum):
    """What an event did to a hand-over or a gate."""

    WROTE = "wrote"
    PASS = "pass"
    #: every check passed and a person is asked — the file holds, though the gate has not passed yet
    HELD = "held"
    FAIL = "fail"
    OUTDATED = "outdated"


class MarkName(Value):
    """What a mark is about: a hand-over's file name (`build.md`) or a gate's stage (`build`)."""

    value: str


class Seq(Value):
    """An event's number in the story's journal — 0 where no event says it."""

    value: int


class JournalMarks(Value):
    """The latest event's number for each kind and name the journal holds."""

    seqs: typing.Mapping[typing.Tuple[MarkKind, MarkName], Seq]

    def at(self, kind: MarkKind, name: MarkName) -> Seq:
        return self.seqs.get((kind, name), Seq(0))

    def has(self, kind: MarkKind, name: MarkName) -> typing.Optional[Seq]:
        return self.seqs.get((kind, name))
