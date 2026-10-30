"""Where an element of the workflow sends a story: a rule's outcome names the stage the story goes to, the stage it
was at once more, or the end of the run — the run jumps where the rules say, never where its own code would."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .stage import StageName

AGAIN, STOP = "again", "stop"


class RuleName(Value):
    """A rule's id as the rulebook knows it — `GATE-RED-PROOF`, `RUN-BACK-1`."""

    value: str


class Target(Value):
    """Where an outcome sends the story: a stage's name, `again` (the stage it was at) or `stop` (a person looks)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("a target names a stage, again or stop")


class Jump(Value):
    """What one rule says for the outcome it came to: its targets, in the order it names them — none where it says
    nothing about where the story goes, which is `again`."""

    rule: RuleName
    targets: typing.Tuple[Target, ...] = ()


class Next(Value):
    """Where the story goes: a stage, or nowhere (`stage` None) — the run ends and a person looks. `rule` is the
    rule that sent it there."""

    stage: typing.Optional[StageName]
    rule: RuleName
