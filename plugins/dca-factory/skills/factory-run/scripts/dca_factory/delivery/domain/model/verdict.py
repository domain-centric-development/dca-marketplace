"""What a gate's check finds: one finding a line, each passed, failed, skipped, noted or waiting for a person."""

from __future__ import annotations

import dataclasses
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


@dataclasses.dataclass(frozen=True)
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


@dataclasses.dataclass(frozen=True)
class Said(Value):
    """What a check says: for a refusal, the stage's next instruction."""

    value: str


@dataclasses.dataclass(frozen=True)
class Finding(Value):
    state: FindingState
    check: CheckName
    said: Said


Findings = typing.Tuple[Finding, ...]
