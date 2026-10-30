"""A rule of the workflow: what a gate check, a pass action or a runner's decision holds a story to, how it can come
out, and where each outcome sends the story — loaded from the rules' repository, bound by its id to the code that
checks or decides it.

    GATE-<CHECK>        what a gate check holds — one rule per name it reports under (`GATE-HAPPY-PATH` under `plan`)
    RUN-<AREA>-<n>      what the runner decides — the route, the rounds, the schedule, the requests, the tools

What a stage is told (`STAGE-…`) stands in its skill, not here. An id is stable: a rule that goes stays, retired, with
the reason, as the rule libraries keep theirs.
"""

from __future__ import annotations

import enum
import typing

from ....building_blocks import AggregateRoot, Value
from .jump import AGAIN, Jump, RuleId, STOP, Target
from .stage import PIPELINE, StageName, StoryKind
from .verdict import CheckName

#: Every name a `goes` may give: a stage of the table, `again`, `stop`.
TARGETS = frozenset([s.name.value for s in PIPELINE] + [AGAIN, STOP])


class RulePart(enum.Enum):
    """What kind of code binds the rule: a gate check, what a passing gate does, or a decision."""

    CHECK = "check"
    PASS = "pass"
    DECISION = "decision"


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


class Outcome(Value):
    """One way the rule comes out: what it means, and where it sends the story — none: where it was."""

    state: OutcomeState
    said: RuleText
    goes: typing.Tuple[Target, ...] = ()

    def __post_init__(self) -> None:
        unknown = sorted(t.value for t in self.goes if t.value not in TARGETS)
        if unknown:
            raise ValueError(f"an outcome goes to {', '.join(unknown)} — no stage, again or stop")


class WorkflowRule(AggregateRoot[RuleId]):
    """One rule: its id, the code that binds it, when it applies, why, its outcomes — and the stages, kinds and
    report names that narrow it where it is narrower than the code that binds it. A retired rule keeps its id and
    says why, with no outcome."""

    def __init__(self, rule_id: RuleId, part: RulePart, when: RuleText, why: RuleText,
                 outcomes: typing.Sequence[Outcome] = (), reports: typing.Sequence[CheckName] = (),
                 stages: typing.Sequence[StageName] = (), kinds: typing.Sequence[StoryKind] = (),
                 retired: typing.Optional[RuleText] = None, written: typing.Optional[Written] = None) -> None:
        super().__init__()
        states = [o.state for o in outcomes]
        if retired is None and not outcomes:
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

    def jump(self, state: OutcomeState) -> Jump:
        """Where the rule sends the story on <state>: its targets — none where it says nothing about where."""
        found = next((o for o in self._outcomes if o.state is state), None)
        return Jump(self._id, found.goes if found is not None else ())
