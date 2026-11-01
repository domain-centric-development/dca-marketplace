"""Show the rulebook: the rules, at a stage or for a kind or all of them, each kind's flow, the rules outside every
stage, and what does not hold in the rulebook itself."""

from __future__ import annotations

import dataclasses
import typing

from ...building_blocks import UseCase
from ..domain.model.rule import KindName, Rule, StageName
from ..domain.model.rulebook import FlowEdge, FlowGraph, FlowStep, Rulebook
from .shared.decided_rules import DecidedRules
from .shared.gate_findings import GateFindings
from .shared.instructed_rules import InstructedRules

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowRulebookQuery:
    """`stage`, `kind`: narrow the rules to one stage, one kind; None — every one."""

    stage: typing.Optional[str] = None
    kind: typing.Optional[str] = None
    #: a story whose gate runs mark the rules that fired
    story: typing.Optional[str] = None


class ShowRulebookInputPort(UseCase[ShowRulebookQuery, Model], typing.Protocol):
    """The rulebook, as a read model."""


def rule_model(rule: Rule) -> Model:
    return dict(id=rule.id.value, title=rule.title.value, enforcement=rule.enforcement.value, part=rule.part.value,
                stages=[s.value for s in rule.stages], kinds=[k.value for k in rule.kinds], when=rule.trigger.value,
                outcomes=[dict(state=o.state.value, said=o.said.value, goes=[t.value for t in o.goes])
                          for o in rule.outcomes],
                why=rule.reason.value, text=rule.text.value, reports=[w.value for w in rule.reports],
                source=rule.source.value, bound=rule.bound.value, state=rule.state.value)


def ids(rules: typing.Tuple[Rule, ...]) -> typing.List[str]:
    return [r.id.value for r in rules]


def step_model(step: FlowStep) -> Model:
    return dict(stage=step.stage.value, gate=step.gate.value, window=step.window.value,
                gate_before=ids(step.gate_before), told=ids(step.told), gate_after=ids(step.gate_after),
                passed=ids(step.passed), decided=ids(step.decided))


def edge_model(edge: FlowEdge) -> Model:
    return dict(source=edge.source.value, target=edge.target.value, way=edge.way.value,
                rules=[dict(rule=r.rule.value, state=r.state.value) for r in edge.rules])


def graph_model(graph: FlowGraph) -> Model:
    """The kind's flow as the views draw it: the steps in order with their gates, and the edges."""
    return dict(steps=[dict(stage=s.stage.value, gate=s.gate.value, gate_before=ids(s.gate_before),
                            gate_after=ids(s.gate_after), decided=ids(s.decided)) for s in graph.steps],
                edges=[edge_model(e) for e in graph.edges], every_gate=[edge_model(e) for e in graph.every_gate],
                anywhere=[edge_model(e) for e in graph.anywhere])


class ShowRulebookUseCase:
    """The rules delivery registers and the skills mark, read as one rulebook."""

    def __init__(self, decided: DecidedRules, instructed: InstructedRules, findings: GateFindings) -> None:
        self._decided = decided
        self._instructed = instructed
        self._findings = findings

    def execute(self, query: ShowRulebookQuery) -> Model:
        book = Rulebook(self._decided.rules(), self._decided.rows(),
                        self._decided.orders())
        stage = StageName(query.stage) if query.stage else None
        kind = KindName(query.kind) if query.kind else None
        kinds = (kind,) if kind else book.kinds()
        chosen = book.chosen(stage, kind)
        return dict(
            skills=self._instructed.where(),
            stage=query.stage, kind=query.kind,
            stages=[dict(name=row.name.value, about=row.about.value, source=row.source.value) for row in book.rows
                    if stage is None or row.name == stage],
            rules=[rule_model(r) for r in chosen],
            retired=[rule_model(r) for r in book.rules if r not in book.active()],
            flow={k.value: dict(every_gate=ids(book.at_every_gate(k)),
                                edges=[dict(source=e.source.value, target=e.target.value, rule=e.rule.value,
                                            state=e.state.value) for e in book.edges(k)],
                                steps=[step_model(s) for s in book.flow(k) if stage is None or s.stage == stage],
                                graph=graph_model(book.graph(k)))
                  for k in kinds},
            outside=[r.id.value for r in book.outside() if r in chosen],
            problems=[p.said.value for p in book.problems(self._instructed.citations(), self._instructed.rules())],
            story=self._story(book, query.story) if query.story else None,
        )

    def _story(self, book: Rulebook, story: str) -> Model:
        """Per rule, how it came out at each stage of the story's last gate runs, and how often it refused."""
        fired: typing.Dict[str, typing.List[Model]] = {}
        for item in book.fired(self._findings.fired(story)):
            states = fired.setdefault(item.rule.value, [])
            entry = dict(stage=item.stage.value, state=item.state.value)
            if entry not in states:
                states.append(entry)
        return dict(id=story, fired=fired,
                    refused={r.rule.value: r.times.value for r in book.refused(self._findings.refused(story))})
