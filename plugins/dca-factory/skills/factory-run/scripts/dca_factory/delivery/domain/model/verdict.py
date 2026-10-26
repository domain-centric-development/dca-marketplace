"""What a gate's check finds: one finding a line, each passed, failed, skipped, noted or waiting for a person."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value


class FindingState(enum.Enum):
    """How a check came out: `pass`; `fail` refuses the stage; `skip` leaves the check unproven; `note` is a fact
    worth reading that fails nothing; `wait` holds the story for a person's answer."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    NOTE = "note"
    WAIT = "wait"


#: Checks about how a hand-over is written rather than whether the work is right: a refusal by one of them costs a
#: round without the code being wrong. The journal names every refusal's checks; reports count the two apart.
FORM_CHECKS = ("files-listed", "story-pass", "tests-mapped", "test-titles", "plan-levels", "levels", "documented",
               "decisions", "reviews", "layout")


class CheckName(Value):
    """The name a check reports under — `story`, `contract`, `happy-path`."""

    value: str

    def ok(self, said: Said) -> Finding:
        return Finding(FindingState.PASS, self, said)

    def fail(self, said: Said) -> Finding:
        return Finding(FindingState.FAIL, self, said)

    def skip(self, said: Said) -> Finding:
        return Finding(FindingState.SKIP, self, said)

    def note(self, said: Said) -> Finding:
        return Finding(FindingState.NOTE, self, said)

    def wait(self, said: Said) -> Finding:
        return Finding(FindingState.WAIT, self, said)


class Said(Value):
    """What a check says: for a refusal, the stage's next instruction."""

    value: str


class Finding(Value):
    state: FindingState
    check: CheckName
    said: Said


Findings = typing.Tuple[Finding, ...]


class RefusalKind(enum.Enum):
    """What a refused gate cost: `form` — every check it names is about how a hand-over is written, a round spent
    with the work right —, else `substance`."""

    FORM = "form"
    SUBSTANCE = "substance"

    @staticmethod
    def of(failed: typing.Tuple[CheckName, ...]) -> RefusalKind:
        return RefusalKind.FORM if failed and all(check.value in FORM_CHECKS for check in failed) \
            else RefusalKind.SUBSTANCE
