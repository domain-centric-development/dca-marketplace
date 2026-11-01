"""The rulebook: every rule, the stage table they are placed in, and the flow of a story of each kind — per stage the
gate before it, what it is told, the gate after it, what a passing gate does and what the runner decides there."""

from __future__ import annotations

import collections
import enum
import typing

from ....building_blocks import Value
from .rule import (
    AGAIN, Citation, Count, Enforcement, Fired, KindName, OutcomeState, Part, Refused, Rule, RuleId, RuleState, Source,
    StageName,
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
    #: what the stage is for, and the file it is written in
    about: Words = Words("")
    source: Source = Source("")


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


class Way(enum.Enum):
    """How an edge of the drawn flow moves a story: on to a later step, once more into the same stage, back to an
    earlier one, to a stop (exit 1), or to a person who answers (exit 3)."""

    ON = "on"
    AGAIN = "again"
    BACK = "back"
    STOP = "stop"
    WAITS = "waits"


#: Where an edge may end beside a step — a person answers, the story is delivered — and where one may start beside a
#: step: at every gate of the flow, anywhere in the run.
WAITS, DELIVERED, EVERY_GATE, ANYWHERE = "waits", "delivered", "every-gate", "anywhere"

#: The outcomes after which a person answers rather than the run ending.
WAITING = (OutcomeState.WAIT, OutcomeState.ASK)


class Ruled(Value):
    """A rule and the outcome of it an edge stands for."""

    rule: RuleId
    state: OutcomeState


class FlowEdge(Value):
    """An edge of the drawn flow: from a step (or every gate, or anywhere) to a step, `stop`, `waits` or `delivered`,
    the way it moves the story, and the rules whose outcomes take it — none for the plain way on."""

    source: StageName
    target: StageName
    way: Way
    rules: typing.Tuple[Ruled, ...]


class FlowGraph(Value):
    """A kind's flow as a graph: its steps in order, the edges between them, and the edges every gate and the whole
    run share — said once, not at each step."""

    kind: KindName
    steps: typing.Tuple[FlowStep, ...]
    edges: typing.Tuple[FlowEdge, ...]
    every_gate: typing.Tuple[FlowEdge, ...]
    anywhere: typing.Tuple[FlowEdge, ...]


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

    def graph(self, kind: KindName) -> FlowGraph:
        """The kind's flow as a graph, from the rules alone: each outcome's place becomes an edge — on, again, back,
        stop or waits — the plain way on between the steps is added, and what every gate or the whole run holds is
        kept apart from the steps."""
        steps = self.flow(kind)
        names = [step.stage for step in steps]
        everywhere = {r.id for r in self.at_every_gate(kind)}

        def way(source: StageName, target: StageName, state: OutcomeState) -> Way:
            if target.value == STOP:
                return Way.WAITS if state in WAITING else Way.STOP
            if target == source or source.value in (EVERY_GATE, ANYWHERE):
                return Way.AGAIN
            return Way.BACK if names.index(target) < names.index(source) else Way.ON

        def ending(target: StageName, state: OutcomeState) -> StageName:
            return StageName(WAITS) if target.value == STOP and state in WAITING else target

        found: typing.Dict[typing.Tuple[str, str, Way], typing.List[Ruled]] = {}
        shared: typing.Dict[typing.Tuple[str, str, Way], typing.List[Ruled]] = {}
        for edge in self.edges(kind):
            source = StageName(EVERY_GATE) if edge.rule in everywhere else edge.source
            target = ending(edge.target, edge.state)
            if edge.rule in everywhere and target.value not in (STOP, WAITS):
                target = source
            bucket = shared if edge.rule in everywhere else found
            ruled = bucket.setdefault((source.value, target.value, way(source, edge.target, edge.state)), [])
            if Ruled(edge.rule, edge.state) not in ruled:
                ruled.append(Ruled(edge.rule, edge.state))
        for here, there in zip(names, names[1:] + [StageName(DELIVERED)]):
            found.setdefault((here.value, there.value, Way.ON), [])
        anywhere: typing.Dict[typing.Tuple[str, str, Way], typing.List[Ruled]] = {}
        for rule in self.outside():
            if not rule.holds_for(kind) or rule.stages:
                continue
            for outcome in rule.outcomes:
                for target in outcome.goes:
                    to = StageName(ANYWHERE) if target.value == AGAIN else ending(target, outcome.state)
                    anywhere.setdefault((ANYWHERE, to.value, way(StageName(ANYWHERE), target, outcome.state)),
                                        []).append(Ruled(rule.id, outcome.state))

        def built(edges: typing.Dict[typing.Tuple[str, str, Way], typing.List[Ruled]]) -> typing.Tuple[FlowEdge, ...]:
            return tuple(FlowEdge(StageName(s), StageName(t), w, tuple(r)) for (s, t, w), r in edges.items())

        return FlowGraph(kind, steps, built(found), built(shared), built(anywhere))

    def unrounded(self) -> typing.Iterator[Problem]:
        """A stage whose gate runs after it, at which no rule sends a refusal back into it: the drawn flow would have
        no round there, and a refused gate no way on."""
        for row in self.rows:
            if row.gate is not GateTime.AFTER:
                continue
            rounds = any(o.state is OutcomeState.FAIL and any(t.value in (AGAIN, row.name.value) for t in o.goes)
                         for r in self.active() if r.holds_at(row.name) for o in r.outcomes)
            if not rounds:
                yield Problem(Words(f"{row.name.value} has a gate after it, but no rule sends a refusal there "
                                    f"`again` — name it in a round rule's `stages:`"))

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

    def problems(self, citations: typing.Tuple[Citation, ...],
                 marked: typing.Tuple[Rule, ...] = ()) -> typing.Tuple[Problem, ...]:
        """An id used twice, a stage no row has, a cited id no rule has, a retired rule still written somewhere — and a
        skill that still marks a paragraph as a told rule (<marked>)."""
        found = list(self.drifted(marked)) + list(self.unrounded())
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
            if rule.part is not Part.INSTRUCTION and not rule.title.value:
                found.append(Problem(Words(f"{rule.id.value} has no `title:` — a person reads a rule by its name, "
                                           f"a short statement of what holds — {rule.source.value}")))
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


    def drifted(self, marked: typing.Tuple[Rule, ...]) -> typing.Iterator[Problem]:
        """A skill that still carries a told rule's marker: the words stand in the rule's file, placed by its stage's
        frame — a copy in a skill drifts from them."""
        for mark in marked:
            yield Problem(Words(f"{mark.id.value} is marked in {mark.source.value} — a told rule's words stand in "
                                f"its file and its stage's frame, never in a skill"))


#: The places a rule may name beside the stage table: the commit hook and CI, a discovery's report.
OUTSIDE_PLACES = ("commit", "discover")
