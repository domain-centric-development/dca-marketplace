"""A story's refused gates in the order the runner met them, with the fresh restarts between them: whether the last
refusal repeats the one before — the same stage, the same failed checks, the same failing tests; the report's text is
never compared, it carries times and paths — and whether a fresh restart came between the two."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .stage import StageName
from .story_words import Selector
from .verdict import CheckName


class GateRefusal(Value):
    """One refused gate the runner met: the stage, the checks that failed, the failing tests its report named."""

    stage: StageName
    checks: typing.FrozenSet[CheckName]
    tests: typing.FrozenSet[Selector]

    def repeats(self, earlier: GateRefusal) -> bool:
        """Whether this refusal is <earlier> again: the same stage, the same failed checks, the same failing tests."""
        return (self.stage, self.checks, self.tests) == (earlier.stage, earlier.checks, earlier.tests)


class FreshRestart(Value):
    """A round the runner started fresh at <stage>, after a refusal repeated the one before."""

    stage: StageName


class Repetition(enum.Enum):
    """What the last refusal is against the one before: new, a repeat, or a repeat after the fresh restart between
    them."""

    NEW = "new"
    REPEATED = "repeated"
    REPEATED_AFTER_FRESH = "repeated-after-fresh"


class RefusalHistory(Value):
    """The story's refusals and fresh restarts since its rounds were last counted from nought, oldest first."""

    entries: typing.Tuple[typing.Union[GateRefusal, FreshRestart], ...]

    def repetition(self) -> Repetition:
        """The last refusal against the one before it."""
        refusals = [(at, entry) for at, entry in enumerate(self.entries) if isinstance(entry, GateRefusal)]
        if len(refusals) < 2:
            return Repetition.NEW
        (before, earlier), (after, last) = refusals[-2:]
        if not last.repeats(earlier):
            return Repetition.NEW
        fresh = any(isinstance(entry, FreshRestart) for entry in self.entries[before + 1:after])
        return Repetition.REPEATED_AFTER_FRESH if fresh else Repetition.REPEATED
