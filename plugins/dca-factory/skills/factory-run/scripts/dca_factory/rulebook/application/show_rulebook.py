"""Show the rulebook: the rules, at a stage or for a kind or all of them, each kind's flow, the rules outside every
stage, and what does not hold in the rulebook itself."""

from __future__ import annotations

import dataclasses
import typing

from ...building_blocks import UseCase
from ..domain.model.rule import KindName, Rule, StageName, Words
from ..domain.model.rulebook import FlowEdge, FlowGraph, FlowStep, Rulebook
from ..domain.model.runs import Journals, ProjectRefusals, StoryRun, story_run
from ..domain.model.track import TileTurn, Track
from .shared.decided_rules import DecidedRules
from .shared.gate_findings import GateFindings
from .shared.instructed_rules import InstructedRules
from .shared.project_journals import ProjectJournals

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
                source=rule.source.value, bound=rule.bound.value, state=rule.state.value,
                restart=dict(stage=rule.restart.stage.value, when=rule.restart.when.value) if rule.restart else None)


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


def track_model(track: Track) -> Model:
    """A kind's track as the page draws it: its tiles, its ways back, whether its delivered end waits for acceptance."""
    return dict(tiles=[dict(stage=t.stage.value, rounds=t.turn is TileTurn.ROUNDS, decides=t.turn is TileTurn.DECIDES,
                            restarts=[r.value for r in t.restarts], restart_when=[w.value for w in t.restart_when])
                       for t in track.tiles],
                ways=[dict(source=w.source.value, target=w.target.value, cost=w.cost.value,
                           rules=[r.value for r in w.rules], reason=w.reason.value) for w in track.ways],
                accepted=track.accepted(), round_limit=track.round_limit.value)


def refusals_model(found: ProjectRefusals) -> Model:
    return dict(rules={r.rule.value: dict(times=r.times.value, last=r.last.value,
                                          stories={s.story.value: s.times.value for s in r.stories},
                                          stages={s.stage.value: s.times.value for s in r.stages})
                       for r in found.rules},
                unnamed=found.unnamed.value, stories=[s.value for s in found.stories])


def run_model(run: StoryRun, book: Rulebook) -> Model:
    """A story's run along its track — and, per rule, how often it refused the story between the stages."""
    refused: typing.Dict[str, int] = {}
    for stage in run.stages:
        for check in stage.checks:
            for rule in book.active():
                if check.check in rule.reports and (not rule.stages or rule.holds_at(stage.stage)):
                    refused[rule.id.value] = refused.get(rule.id.value, 0) + check.times.value
    return dict(kind=run.kind.value, last=run.last.value, reading=run.reading.value,
                stages={s.stage.value: dict(reached=s.reached, ended=s.ended.value if s.ended else None,
                                            refused=s.refused.value, unnamed=s.unnamed.value, tries=s.tries.value,
                                            checks={c.check.value: c.times.value for c in s.checks})
                        for s in run.stages},
                ways=[dict(source=w.source.value, target=w.target.value, times=w.times.value) for w in run.ways],
                restarts={r.stage.value: dict(times=r.times.value, reasons=[w.value for w in r.reasons])
                          for r in run.restarts},
                refused=refused)


class ShowRulebookUseCase(ShowRulebookInputPort):
    """The rules delivery registers and the skills mark, read as one rulebook."""

    def __init__(self, decided: DecidedRules, instructed: InstructedRules, findings: GateFindings,
                 journals: ProjectJournals) -> None:
        self._decided = decided
        self._instructed = instructed
        self._findings = findings
        self._journals = journals

    def execute(self, query: ShowRulebookQuery) -> Model:
        book = Rulebook(self._decided.rules(), self._decided.rows(),
                        self._decided.orders())
        stage = StageName(query.stage) if query.stage else None
        kind = KindName(query.kind) if query.kind else None
        kinds = (kind,) if kind else book.kinds()
        chosen = book.chosen(stage, kind)
        limit = self._decided.round_limit()
        tracks = {k: book.track(k, limit) for k in kinds}
        journals = Journals(self._journals.journals())
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
                                graph=graph_model(book.graph(k)), track=track_model(tracks[k]))
                  for k in kinds},
            refusals=refusals_model(journals.refusals(book.active())),
            outside=[r.id.value for r in book.outside() if r in chosen],
            problems=[p.said.value for p in book.problems(self._instructed.citations(), self._instructed.rules())],
            story=self._story(book, query.story, journals, tracks) if query.story else None,
        )

    def _story(self, book: Rulebook, story: str, journals: Journals,
               tracks: typing.Dict[KindName, Track]) -> Model:
        """Per rule, how it came out at each stage of the story's last gate runs, and how often it refused."""
        fired: typing.Dict[str, typing.List[Model]] = {}
        for item in book.fired(self._findings.fired(story)):
            states = fired.setdefault(item.rule.value, [])
            entry = dict(stage=item.stage.value, state=item.state.value)
            if entry not in states:
                states.append(entry)
        found = self._findings.refused(story)
        refused_at: typing.Dict[str, typing.Dict[str, int]] = {}
        for item in book.refused_at(found):
            at = refused_at.setdefault(item.stage.value, {})
            at[item.rule.value] = at.get(item.rule.value, 0) + 1
        journal = journals.story(Words(story))
        kind = (journal.kind if journal else None) or KindName.STORY
        track = tracks.get(kind) or book.track(kind, self._decided.round_limit())
        return dict(id=story, fired=fired, refused={r.rule.value: r.times.value for r in book.refused(found)},
                    refused_at=refused_at, run=run_model(story_run(journal, track), book) if journal else None)
