"""Show the rulebook: the rules, at a stage or for a kind or all of them, each kind's flow, the rules outside every
stage, and what does not hold in the rulebook itself."""

from __future__ import annotations

import dataclasses
import typing

from ...building_blocks import UseCase
from ..domain.model.rule import KindName, Rule, StageName
from ..domain.model.rulebook import FlowStep, Rulebook
from .shared.decided_rules import DecidedRules
from .shared.instructed_rules import InstructedRules

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowRulebookQuery:
    """`stage`, `kind`: narrow the rules to one stage, one kind; None — every one."""

    stage: typing.Optional[str] = None
    kind: typing.Optional[str] = None


class ShowRulebookInputPort(UseCase[ShowRulebookQuery, Model], typing.Protocol):
    """The rulebook, as a read model."""


def rule_model(rule: Rule) -> Model:
    return dict(id=rule.id.value, enforcement=rule.enforcement.value, part=rule.part.value,
                stages=[s.value for s in rule.stages], kinds=[k.value for k in rule.kinds], when=rule.trigger.value,
                outcomes=[dict(state=o.state.value, said=o.said.value) for o in rule.outcomes],
                why=rule.reason.value, text=rule.text.value, reports=[w.value for w in rule.reports],
                source=rule.source.value, state=rule.state.value)


def ids(rules: typing.Tuple[Rule, ...]) -> typing.List[str]:
    return [r.id.value for r in rules]


def step_model(step: FlowStep) -> Model:
    return dict(stage=step.stage.value, gate=step.gate.value, window=step.window.value,
                gate_before=ids(step.gate_before), told=ids(step.told), gate_after=ids(step.gate_after),
                passed=ids(step.passed), decided=ids(step.decided))


class ShowRulebookUseCase:
    """The rules delivery registers and the skills mark, read as one rulebook."""

    def __init__(self, decided: DecidedRules, instructed: InstructedRules) -> None:
        self._decided = decided
        self._instructed = instructed

    def execute(self, query: ShowRulebookQuery) -> Model:
        book = Rulebook(self._decided.rules() + self._instructed.rules(), self._decided.rows(),
                        self._decided.orders())
        stage = StageName(query.stage) if query.stage else None
        kind = KindName(query.kind) if query.kind else None
        kinds = (kind,) if kind else book.kinds()
        chosen = book.chosen(stage, kind)
        return dict(
            skills=self._instructed.where(),
            stage=query.stage, kind=query.kind,
            rules=[rule_model(r) for r in chosen],
            retired=[rule_model(r) for r in book.rules if r not in book.active()],
            flow={k.value: dict(every_gate=ids(book.at_every_gate(k)),
                                steps=[step_model(s) for s in book.flow(k) if stage is None or s.stage == stage])
                  for k in kinds},
            outside=[r.id.value for r in book.outside() if r in chosen],
            problems=[p.said.value for p in book.problems(self._instructed.citations())],
        )
