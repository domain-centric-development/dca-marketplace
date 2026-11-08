"""Where an element of the workflow sends a story: a rule's outcome names the stage the story goes to, the stage it
was at once more, or the end of the run — the run jumps where the rules say, never where its own code would."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Id, Value
from .stage import StageName

AGAIN, STOP = "again", "stop"
RULE_ID = re.compile(r"^(GATE|RUN|STAGE)(-[A-Z0-9]+)+$")


class RuleId(Id):
    """A rule's id — `GATE-RED-PROOF`, `RUN-BACK-1`, `STAGE-BUILD-1`."""

    value: str

    def __post_init__(self) -> None:
        if not RULE_ID.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no rule id — GATE-<CHECK>, RUN-<AREA>-<n> or STAGE-<STAGE>-<n>")


class Target(Value):
    """Where an outcome sends the story: a stage's name, `again` (the stage it was at) or `stop` (a person looks)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("a target names a stage, again or stop")


class Jump(Value):
    """What one rule says for the outcome it came to: its targets, in the order it names them — none where it says
    nothing about where the story goes, which is `again`."""

    rule: RuleId
    targets: typing.Tuple[Target, ...] = ()


class Next(Value):
    """Where the story goes: a stage, or nowhere (`stage` None) — the run ends and a person looks. `rule` is the
    rule that sent it there."""

    stage: typing.Optional[StageName]
    rule: RuleId


class Jumped(Value):
    """A way back the run took: from the stage that sent the story to the stage it runs again from, by the rule that
    said so — what the journal keeps, so a reader never guesses it from the order of the gates."""

    source: StageName
    target: StageName
    rule: RuleId


class RestartReason(enum.Enum):
    """Why a run started anew at a stage instead of going on: the story changed under its plan, a test changed after
    it was seen red, the plan found the whole story holding already."""

    STORY_CHANGED = "story-changed"
    TEST_CHANGED = "test-changed"
    ADOPTED = "adopted"


class Restarted(Value):
    """A run started anew at a stage — a re-entry, no round spent —, by the rule that said so, and why."""

    stage: StageName
    rule: RuleId
    reason: RestartReason
