"""A rule of the factory: its id, who holds it, when it applies, how it comes out, why it exists, where it is written."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Id, Value

RULE_ID = re.compile(r"^(GATE|RUN|STAGE)(-[A-Z0-9]+)+$")


class RuleId(Id):
    """A rule's id, stable for its life and after: `GATE-<CHECK>`, `STAGE-<STAGE>-<n>`, `RUN-<AREA>-<n>`."""

    value: str

    def __post_init__(self) -> None:
        if not RULE_ID.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no rule id — GATE-<CHECK>, STAGE-<STAGE>-<n> or RUN-<AREA>-<n>")

    def area(self) -> Words:
        """What the id names after its prefix's first part: the check, the stage or the runner's area."""
        return Words(self.value.split("-")[1])


class Enforcement(enum.Enum):
    """Who holds a rule: the gate decides it, the runner decides it, or a stage is told it."""

    GATE = "gate"
    RUNNER = "runner"
    INSTRUCTED = "instructed"

    @staticmethod
    def of(rule_id: RuleId) -> Enforcement:
        prefix = rule_id.value.split("-")[0]
        return {"GATE": Enforcement.GATE, "RUN": Enforcement.RUNNER}.get(prefix, Enforcement.INSTRUCTED)


class Part(enum.Enum):
    """Where a rule sits in a story's flow: a gate's check, what a passing gate does, a decision of the runner or of
    the gate outside a stage, or what a stage is told."""

    CHECK = "check"
    PASS_ACTION = "pass"
    DECISION = "decision"
    INSTRUCTION = "instruction"


class OutcomeState(enum.Enum):
    """How a rule can come out: `ask` writes a decision record and stops."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    NOTE = "note"
    WAIT = "wait"
    ASK = "ask"


class RuleState(enum.Enum):
    """A rule in force, or one that went — its id kept, never given to another."""

    ACTIVE = "active"
    RETIRED = "retired"


class Words(Value):
    """A rule's words: when it applies, why it exists, what an outcome says, what a stage is told."""

    value: str


class StageName(Value):
    """A stage of the pipeline, or a place outside it — `commit`, `discover`."""

    value: str


class KindName(enum.Enum):
    """A story kind, as the rulebook names the kinds its rules hold for."""

    STORY = "story"
    JOURNEY = "journey"
    ADOPT = "adopt"
    TASK = "task"


class Source(Value):
    """Where a rule is written, or where code binds it: a file, or `<path>:<line>`."""

    value: str


#: Where an outcome may send the story beside a stage: the refused stage once more, or nowhere — a person looks.
AGAIN, STOP = "again", "stop"


class Outcome(Value):
    """How a rule comes out, what it says then, and where the story goes — stages, `again`, `stop`; none: on."""

    state: OutcomeState
    said: Words
    goes: typing.Tuple[StageName, ...] = ()


class Restart(Value):
    """Where a rule starts a story's run anew — a re-entry, never a jump back: no round is spent — and on what."""

    stage: StageName
    when: Words


class Rule(Value):
    """One rule. A gate's or the runner's says its outcomes; an instructed one says what the stage is told (`text`).
    No stages — it is placed in no stage of the flow; no kinds — it holds for every kind."""

    id: RuleId
    part: Part
    stages: typing.Tuple[StageName, ...]
    kinds: typing.Tuple[KindName, ...]
    trigger: Words
    outcomes: typing.Tuple[Outcome, ...]
    reason: Words
    text: Words
    reports: typing.Tuple[Words, ...]
    source: Source
    state: RuleState = RuleState.ACTIVE
    #: the code that checks or decides it — a gate's or the runner's rule; none for an instructed one
    bound: Source = Source("")
    #: its name for a person, a short statement of what holds; empty where the file names none
    title: Words = Words("")
    #: where it starts the run anew, and on what; none for a rule that restarts nothing
    restart: typing.Optional[Restart] = None

    @property
    def enforcement(self) -> Enforcement:
        return Enforcement.of(self.id)

    def holds_at(self, stage: StageName) -> bool:
        return stage in self.stages

    def holds_for(self, kind: KindName) -> bool:
        return not self.kinds or kind in self.kinds


class Citation(Value):
    """A rule id a skill names in its text, and where."""

    id: Words
    source: Source


class Count(Value):
    value: int


class Moment(Value):
    """When a journal line was written, as the journal writes it (ISO 8601, UTC)."""

    value: str


class Fired(Value):
    """What the gate reported under one name at one stage of a story's last run there."""

    stage: StageName
    check: Words
    state: OutcomeState


class Refused(Value):
    """How often the gate refused a story for one name — at one stage, or over all of them where none is named."""

    check: Words
    times: Count
    stage: StageName = StageName("")
