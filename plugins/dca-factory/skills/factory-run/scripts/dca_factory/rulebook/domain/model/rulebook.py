"""The rulebook: every rule, the stage table they are placed in, and the flow of a story of each kind — per stage the
gate before it, what it is told, the gate after it, what a passing gate does and what the runner decides there."""

from __future__ import annotations

import collections
import enum
import typing

from ....building_blocks import Value
from .rule import (
    AGAIN, Citation, Count, Enforcement, Fired, KindName, OutcomeState, Part, Refused, Rule, RuleId, RuleState, StageName,
    STOP, Words)


class GateTime(enum.Enum):
    """When a stage's gate runs: before the stage (the plan's), after its file is written, or not at all (the judge's
    verdict is read at the next gate)."""

    BEFORE = "before"
    AFTER = "after"
    NONE = "none"


class OrderPlace(enum.Enum):
    """A step of a kind's run order, or a step after it (adopt, integrate)."""

    IN_ORDER = "in-order"
    AFTER_ORDER = "after-order"


class StageRow(Value):
    name: StageName
    kinds: typing.Tuple[KindName, ...]
    gate: GateTime
    place: OrderPlace
    window: Words


class KindOrder(Value):
    kind: KindName
    stages: typing.Tuple[StageName, ...]


class FlowStep(Value):
    """One stage of a kind's flow, the rules in the order they come: the gate before it, what the stage is told, the
    gate after it, what a passing gate does, what the runner decides there."""

    stage: StageName
    gate: GateTime
    window: Words
    gate_before: typing.Tuple[Rule, ...]
    told: typing.Tuple[Rule, ...]
    gate_after: typing.Tuple[Rule, ...]
    passed: typing.Tuple[Rule, ...]
    decided: typing.Tuple[Rule, ...]


class Edge(Value):
    """Where an outcome of a rule at one stage sends the story: another stage (back, or on), the same one again, or
    `stop`."""

    source: StageName
    target: StageName
    rule: RuleId
    state: OutcomeState


class RuleFired(Value):
    """A rule at a stage of one story, as the gate's last run there came out."""

    rule: RuleId
    stage: StageName
    state: OutcomeState


class RuleRefused(Value):
    rule: RuleId
    times: Count


class Problem(Value):
    """What does not hold in the rulebook itself, in a sentence."""

    said: Words


class Rulebook(Value):
    """All rules and the table they are placed in."""

    rules: typing.Tuple[Rule, ...]
    rows: typing.Tuple[StageRow, ...]
    orders: typing.Tuple[KindOrder, ...]

    def active(self) -> typing.Tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.state is RuleState.ACTIVE)

    def chosen(self, stage: typing.Optional[StageName], kind: typing.Optional[KindName]) -> typing.Tuple[Rule, ...]:
        """The active rules at a stage and for a kind — either left out, all of them."""
        return tuple(r for r in self.active() if (stage is None or r.holds_at(stage))
                     and (kind is None or r.holds_for(kind)))

    def kinds(self) -> typing.Tuple[KindName, ...]:
        return tuple(order.kind for order in self.orders)

    def steps(self, kind: KindName) -> typing.Tuple[StageName, ...]:
        """The kind's stages in its run order, then the steps after it that the kind takes."""
        order = next((o.stages for o in self.orders if o.kind == kind), ())
        return order + tuple(row.name for row in self.rows if row.place is OrderPlace.AFTER_ORDER and kind in row.kinds)

    def at_every_gate(self, kind: KindName) -> typing.Tuple[Rule, ...]:
        """The checks every gate of the kind's flow holds — said once, not at each stage."""
        gated = [name for name in self.steps(kind) if self.row(name).gate is not GateTime.NONE]
        return tuple(r for r in self.chosen(None, kind)
                     if r.part is Part.CHECK and gated and all(r.holds_at(name) for name in gated))

    def row(self, name: StageName) -> StageRow:
        return next(row for row in self.rows if row.name == name)

    def flow(self, kind: KindName) -> typing.Tuple[FlowStep, ...]:
        """Each step of the kind with its rules — the checks every gate holds left to `at_every_gate`."""
        everywhere = set(self.at_every_gate(kind))
        steps = []
        for name in self.steps(kind):
            row = self.row(name)
            here = [r for r in self.chosen(name, kind)]
            checks = tuple(r for r in here if r.part is Part.CHECK and r not in everywhere)
            steps.append(FlowStep(
                name, row.gate, row.window,
                checks if row.gate is GateTime.BEFORE else (),
                tuple(r for r in here if r.part is Part.INSTRUCTION),
                checks if row.gate is GateTime.AFTER else (),
                tuple(r for r in here if r.part is Part.PASS_ACTION),
                tuple(r for r in here if r.part is Part.DECISION)))
        return tuple(steps)

    def edges(self, kind: KindName) -> typing.Tuple[Edge, ...]:
        """Every place an outcome sends the story to, from the stage its rule sits at: `again` back to that stage."""
        steps = self.steps(kind)
        found = []
        for stage in steps:
            for rule in self.chosen(stage, kind):
                for outcome in rule.outcomes:
                    for target in outcome.goes:
                        to = stage if target.value == AGAIN else target
                        if to in steps or to.value == STOP:
                            found.append(Edge(stage, to, rule.id, outcome.state))
        return tuple(found)

    def fired(self, found: typing.Tuple[Fired, ...]) -> typing.Tuple[RuleFired, ...]:
        """Each rule a finding was reported under, at the stage it was reported — a name several rules report under
        counts for each of them; a name no rule has is left out (`problems` names a rule's absence, not a story)."""
        by_name: typing.Dict[Words, typing.List[Rule]] = {}
        for rule in self.active():
            for name in rule.reports:
                by_name.setdefault(name, []).append(rule)
        return tuple(RuleFired(rule.id, item.stage, item.state)
                     for item in found for rule in by_name.get(item.check, ())
                     if not rule.stages or rule.holds_at(item.stage))

    def refused(self, found: typing.Tuple[Refused, ...]) -> typing.Tuple[RuleRefused, ...]:
        """How often the gate refused for each rule's names, summed over them."""
        times: typing.Dict[RuleId, int] = {}
        for item in found:
            for rule in self.active():
                if item.check in rule.reports:
                    times[rule.id] = times.get(rule.id, 0) + item.times.value
        return tuple(RuleRefused(rule_id, Count(n)) for rule_id, n in times.items())

    def outside(self) -> typing.Tuple[Rule, ...]:
        """The active rules no stage of any flow holds: the runner's whole run, the commit hook, every stage alike."""
        staged = {row.name for row in self.rows}
        return tuple(r for r in self.active() if not any(stage in staged for stage in r.stages))

    def problems(self, citations: typing.Tuple[Citation, ...]) -> typing.Tuple[Problem, ...]:
        """An id used twice, a stage no row has, a cited id no rule has, a retired rule still written somewhere."""
        found = []
        counted = collections.Counter(r.id for r in self.rules)
        for rule_id, count in counted.items():
            if count > 1:
                written = ", ".join(r.source.value for r in self.rules if r.id == rule_id)
                found.append(Problem(Words(f"{rule_id.value} is used {count} times — {written}")))
        places = {row.name for row in self.rows}
        for rule in self.active():
            if rule.part is Part.INSTRUCTION and rule.enforcement is not Enforcement.INSTRUCTED:
                found.append(Problem(Words(f"{rule.id.value} in a skill's text — {rule.source.value}: a skill "
                                           f"carries STAGE- ids, the gate and the runner register theirs")))
            unknown = [s.value for s in rule.stages if s not in places and s.value not in OUTSIDE_PLACES]
            if unknown:
                found.append(Problem(Words(f"{rule.id.value} names no stage {', '.join(unknown)} — "
                                           f"{rule.source.value}")))
            if rule.part is not Part.INSTRUCTION and not rule.bound.value:
                found.append(Problem(Words(f"{rule.id.value} is written but no code binds it — it decides nothing; "
                                           f"bind it or retire it — {rule.source.value}")))
            nowhere = [t.value for o in rule.outcomes for t in o.goes if t not in places and t.value not in (AGAIN, STOP)]
            if nowhere:
                found.append(Problem(Words(f"{rule.id.value} goes to no stage {', '.join(nowhere)} — "
                                           f"{rule.source.value}")))
        known = {r.id.value: r for r in self.rules}
        for citation in citations:
            cited = known.get(citation.id.value)
            if cited is None:
                found.append(Problem(Words(f"{citation.source.value} cites {citation.id.value}, which no rule has")))
            elif cited.state is RuleState.RETIRED:
                found.append(Problem(Words(f"{citation.source.value} cites {citation.id.value}, which is retired")))
        return tuple(found)


#: The places a rule may name beside the stage table: the commit hook and CI, a discovery's report.
OUTSIDE_PLACES = ("commit", "discover")
