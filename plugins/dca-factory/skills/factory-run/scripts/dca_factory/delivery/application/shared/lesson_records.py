"""The lesson records: where a candidate is asked, beside the project's own decision records."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.decision_record import RecordId
from ...domain.model.lesson import Candidate, LessonKind, Signals
from ...domain.model.moment import Moment
from .lesson_signals import LessonSignals


class LessonRecords(OutputPort, typing.Protocol):
    """A lesson asked as a record of the project's own: `<product>/decisions/<id>.md`, `kind: lesson`."""

    def taken(self, record: RecordId) -> bool:
        """Whether a record by this id exists already."""
        ...

    def write(self, record: RecordId, candidate: Candidate, asked: Moment) -> str:
        """Write the candidate as a new open lesson record — its evidence, its places as options, the recommended one
        first — and say where, as a person reads it."""
        ...


class LessonProposals:
    """Every candidate the signals make that nobody was asked yet becomes an open lesson record, beside the stories;
    no story waits for it. A candidate asked again after `not now` takes the next free id (`<id>-2`, …)."""

    def __init__(self, signals: LessonSignals, records: LessonRecords) -> None:
        self._signals = signals
        self._records = records

    def propose(self, at: Moment) -> typing.List[typing.Tuple[str, LessonKind, str]]:
        """[(record id, kind, where)] of each record written now."""
        written = []
        for candidate in Signals(tuple(self._signals.signals())).candidates(self._signals.decided()):
            record, n = RecordId(candidate.id.value), 1
            while self._records.taken(record):
                n += 1
                record = RecordId(f"{candidate.id.value}-{n}")
            written.append((record.value, candidate.kind, self._records.write(record, candidate, at)))
        return written
