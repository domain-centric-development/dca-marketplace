"""The judge's confirmed defects as the pipeline weighs them: each row's origin — on a line the story added or changed,
or on code that was there before it — computed from the story's diff, never judged; and what a verdict means once its
rows are weighed: a `changes-requested` whose blocking rows all lie on code the story did not write sends nothing
back, and a `pass` with a blocking row on the story's own lines is no pass."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .story_state import Detail, Judged


class Origin(enum.Enum):
    """Where a confirmed defect lies: on a line the story added or changed, on code it did not write, or at a place
    the diff cannot tell (no line, or a file the pipeline could not read)."""

    INTRODUCED = "introduced"
    PRE_EXISTING = "pre-existing"
    UNRESOLVED = ""


class RoundPlace(enum.Enum):
    """Where a row stands against the round before: the first verdict, a place the previous verdict named, a line the
    story changed since then, or none of these — a new finding on what the round did not touch."""

    FIRST = "first"
    REPEATED = "repeated"
    CHANGED_SINCE = "changed since"
    UNTOUCHED = "untouched"


#: The severities that send a story back; every other one is recorded without blocking.
BLOCKING = ("blocker", "major")


class JudgeRow(Value):
    """A row of the judge's `## Confirmed defects`: its perspective, place (`<file>:<line>`), severity and origin."""

    perspective: Detail
    where: Detail
    severity: Detail
    origin: Origin
    since: RoundPlace = RoundPlace.FIRST

    def blocks(self) -> bool:
        """Whether the row sends a story back: a blocking severity — and from the second round on, only on what the
        round changed or a place the previous verdict named; a new finding on untouched lines is recorded as a minor."""
        return self.severity.value.strip("` *").lower() in BLOCKING and self.since is not RoundPlace.UNTOUCHED


def weighed(judged: Judged, rows: typing.Sequence[JudgeRow]) -> Judged:
    """What the verdict means once its rows are weighed: `changes-requested` whose blocking rows all lie on code the
    story did not write, or — from the second round on — on lines the round did not touch and no earlier verdict named,
    is `pass`: such a defect is recorded, it costs no round. Every other verdict stands as written."""
    severe = [row for row in rows if row.severity.value.strip("` *").lower() in BLOCKING]
    blocking = [row for row in severe if row.blocks()]
    if judged is Judged.AGAIN and severe and all(row.origin is Origin.PRE_EXISTING or not row.blocks()
                                                  for row in severe):
        return Judged.PASS
    if judged is Judged.AGAIN and blocking and all(row.origin is Origin.PRE_EXISTING for row in blocking):
        return Judged.PASS
    return judged


def pass_contradicted(judged: Judged, rows: typing.Sequence[JudgeRow]) -> typing.Tuple[JudgeRow, ...]:
    """The blocking rows on the story's own lines a written `pass` passes over — none where the verdict holds."""
    if judged is not Judged.PASS:
        return ()
    return tuple(row for row in rows if row.blocks() and row.origin is Origin.INTRODUCED)


class FindingOutcome(enum.Enum):
    """What became of a blocking finding by the next verdict: raised again, gone with its line changed, gone with its
    line as it was, or closed by a person's answer."""

    REPEATED = "repeated"
    FIXED = "fixed"
    DROPPED = "dropped"
    OVERRULED = "overruled"


class NextSeen(enum.Enum):
    """What the next verdict showed of a blocking finding: raised again, or gone — its line changed or as it was."""

    RAISED_AGAIN = "raised again"
    GONE_LINE_CHANGED = "gone, line changed"
    GONE_LINE_SAME = "gone, line as it was"


class Closure(enum.Enum):
    """Whether a person's answer closed the finding."""

    OPEN = "open"
    ANSWERED = "answered"


def outcome_of(seen: NextSeen, closure: Closure) -> FindingOutcome:
    """The outcome of a blocking finding at the next verdict — computed, never written by a model: a person's answer
    that closed it overrules it; raised again it repeats; gone, it was fixed where its line changed and dropped where
    it did not."""
    if closure is Closure.ANSWERED:
        return FindingOutcome.OVERRULED
    if seen is NextSeen.RAISED_AGAIN:
        return FindingOutcome.REPEATED
    return FindingOutcome.FIXED if seen is NextSeen.GONE_LINE_CHANGED else FindingOutcome.DROPPED
