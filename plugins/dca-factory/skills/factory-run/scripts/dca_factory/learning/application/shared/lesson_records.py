"""The lesson records: where a candidate is asked, beside the project's own decision records."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.lesson import Candidate, LessonKind, Signals
from ...domain.model.words import Count, Moment, RecordId
from .lesson_signals import LessonSignals


class LessonRecords(OutputPort, typing.Protocol):
    """A lesson asked as a record of the project's own: `<product>/decisions/<id>.md`, `kind: lesson`."""

    def taken(self, record: RecordId) -> bool:
        """Whether a record by this id exists already."""
        ...

    def withdraw(self, record: RecordId) -> None:
        """Remove a lesson record nobody answered — its candidate no longer holds."""
        ...

    def write(self, record: RecordId, candidate: Candidate, asked: Moment) -> str:
        """Write the candidate as a new open lesson record — its evidence, its places as options, the recommended one
        first — and say where, as a person reads it."""
        ...


class LessonProposals:
    """Every candidate the signals make that nobody was asked yet becomes an open lesson record, beside the stories;
    no story waits for it — at most `open_at_once` records open at a time, the most stories first. A candidate asked
    again (after `not now`, or placed and back) takes the next free id (`<id>-2`, …)."""

    def __init__(self, signals: LessonSignals, records: LessonRecords) -> None:
        self._signals = signals
        self._records = records

    def propose(self, at: Moment) -> typing.List[typing.Tuple[str, LessonKind, str]]:
        """[(record id, kind, where)] of each record written now."""
        written = []
        signals = Signals(tuple(self._signals.signals()))
        decided = self._signals.decided()
        stale = signals.stale(decided)
        for lesson in stale:
            if lesson.record is not None:
                self._records.withdraw(RecordId(lesson.record.value))
        decided = [d for d in decided if d not in stale]
        waiting = Count(sum(1 for d in decided if d.place is None))
        drawn = signals.candidates(decided, self._signals.back_after())
        for candidate in signals.bounded(drawn, waiting, self._signals.open_at_once()):
            record, n = RecordId(candidate.id.value), 1
            while self._records.taken(record):
                n += 1
                record = RecordId(f"{candidate.id.value}-{n}")
            written.append((record.value, candidate.kind, self._records.write(record, candidate, at)))
        return written
