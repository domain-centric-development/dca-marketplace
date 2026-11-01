"""A rule of the workflow: what a gate check, a pass action or a runner's decision holds a story to, how it can come
out, and where each outcome sends the story — loaded from the rules' repository, bound by its id to the code that
checks or decides it.

    GATE-<CHECK>        what a gate check holds — one rule per name it reports under (`GATE-HAPPY-PATH` under `plan`)
    RUN-<AREA>-<n>      what the runner decides — the route, the rounds, the schedule, the requests, the tools
    STAGE-<STAGE>-<n>   what a stage is told — its words, the section they stand under, the stages and kinds it holds for

An id is stable: a rule that goes stays, retired, with the reason, as the rule libraries keep theirs.
"""

from __future__ import annotations

import enum
import typing

from ....building_blocks import AggregateRoot, Value
from .jump import Jump, RuleId, Target
from .stage import StageName, StoryKind
from .verdict import CheckName


class RulePart(enum.Enum):
    """What binds the rule: a gate check, what a passing gate does, a decision — or what a stage is told, which no code
    binds: the stage reads it."""

    CHECK = "check"
    PASS = "pass"
    DECISION = "decision"
    TOLD = "told"


class OutcomeState(enum.Enum):
    """How a rule can come out, in the order a reader takes them: `ask` writes a decision record and stops."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    NOTE = "note"
    WAIT = "wait"
    ASK = "ask"


class RuleText(Value):
    """A rule's words for a person: when it applies, why it exists, what an outcome means, why it was retired."""

    value: str


class Written(Value):
    """Where the rule is written, as a person finds it — `workflow/rules/gate/GATE-RED-PROOF.md`."""

    value: str


class RuleOrder(Value):
    """Where a told rule stands among the others its skill carries — the order a stage reads them in."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError(f"order {self.value}: a told rule's place counts from 1")


class Outcome(Value):
    """One way the rule comes out: what it means, and where it sends the story — none: where it was. Whether a target
    is a stage is the workflow's question (`WorkflowRule.unknown_targets`)."""

    state: OutcomeState
    said: RuleText
    goes: typing.Tuple[Target, ...] = ()


class WorkflowRule(AggregateRoot[RuleId]):
    """One rule: its id, the code that binds it, when it applies, why, its outcomes — and the stages, kinds and
    report names that narrow it where it is narrower than the code that binds it. A retired rule keeps its id and
    says why, with no outcome."""

    def __init__(self, rule_id: RuleId, part: RulePart, when: RuleText, why: RuleText,
                 outcomes: typing.Sequence[Outcome] = (), reports: typing.Sequence[CheckName] = (),
                 stages: typing.Sequence[StageName] = (), kinds: typing.Sequence[StoryKind] = (),
                 retired: typing.Optional[RuleText] = None, written: typing.Optional[Written] = None,
                 told: typing.Optional[RuleText] = None, section: typing.Optional[RuleText] = None,
                 see: typing.Optional[Written] = None, order: typing.Optional[RuleOrder] = None,
                 title: typing.Optional[RuleText] = None) -> None:
        super().__init__()
        states = [o.state for o in outcomes]
        if part is RulePart.TOLD:
            if outcomes:
                raise ValueError(f"rule {rule_id.value}: what a stage is told has no outcome")
            if retired is None and (told is None or not told.value.strip()):
                raise ValueError(f"rule {rule_id.value}: tells a stage nothing")
        elif retired is None and not outcomes:
            raise ValueError(f"rule {rule_id.value}: says no outcome")
        if len(states) != len(set(states)):
            raise ValueError(f"rule {rule_id.value}: says an outcome twice")
        self._id = rule_id
        self._part = part
        self._when = when
        self._why = why
        self._outcomes = tuple(sorted(outcomes, key=lambda o: list(OutcomeState).index(o.state)))
        self._reports = tuple(reports)
        self._stages = tuple(stages)
        self._kinds = tuple(kinds)
        self._retired = retired
        self._written = written
        self._told = told
        self._section = section
        self._see = see
        self._order = order
        self._title = title

    @property
    def id(self) -> RuleId:
        return self._id

    @property
    def part(self) -> RulePart:
        return self._part

    @property
    def when(self) -> RuleText:
        return self._when

    @property
    def why(self) -> RuleText:
        return self._why

    @property
    def title(self) -> typing.Optional[RuleText]:
        """The rule's name for a person, a short statement of what holds — none where the file names none."""
        return self._title

    @property
    def outcomes(self) -> typing.Tuple[Outcome, ...]:
        return self._outcomes

    @property
    def reports(self) -> typing.Tuple[CheckName, ...]:
        """The names a gate reports the rule under — none for a runner's decision."""
        return self._reports

    @property
    def stages(self) -> typing.Tuple[StageName, ...]:
        """Where it holds, narrower than the code that binds it; empty: wherever that code holds."""
        return self._stages

    @property
    def kinds(self) -> typing.Tuple[StoryKind, ...]:
        """The kinds it holds for, narrower than the code that binds it; empty: every kind that code holds."""
        return self._kinds

    @property
    def retired(self) -> typing.Optional[RuleText]:
        return self._retired

    @property
    def written(self) -> typing.Optional[Written]:
        return self._written

    @property
    def told(self) -> typing.Optional[RuleText]:
        """What a stage is told, word for word as it reads it — a told rule's alone."""
        return self._told

    @property
    def section(self) -> typing.Optional[RuleText]:
        """The heading a told rule stands under."""
        return self._section

    @property
    def see(self) -> typing.Optional[Written]:
        """Where the rest of a told rule stands that no frame places — a reference every reader reads."""
        return self._see

    @property
    def order(self) -> typing.Optional[RuleOrder]:
        """A told rule's place among the told rules no frame places — None where it has none."""
        return self._order

    def unknown_targets(self, targets: typing.FrozenSet[Target]) -> typing.Tuple[Target, ...]:
        """The targets its outcomes send a story to that are none of <targets> — a workflow's stages, again, stop."""
        return tuple(sorted({t for o in self._outcomes for t in o.goes} - targets, key=lambda t: t.value))

    def jump(self, state: OutcomeState) -> Jump:
        """Where the rule sends the story on <state>: its targets — none where it says nothing about where."""
        found = next((o for o in self._outcomes if o.state is state), None)
        return Jump(self._id, found.goes if found is not None else ())
