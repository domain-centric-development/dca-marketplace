"""Delivery's rules, asked through delivery's open host service and translated into the rulebook's model."""

from __future__ import annotations

import typing

from .....delivery.api.rules import kind_orders, pipeline_rules, stage_rows, story_gate_findings
from ....domain.model.rule import (
    Count, Fired, KindName, Outcome, OutcomeState, Part, Refused, Rule, RuleId, RuleState, Source, StageName, Words)
from ....domain.model.rulebook import GateTime, KindOrder, OrderPlace, StageRow
from ..skills.skill_files import plain

#: How delivery publishes where a rule sits, in the rulebook's terms.
PARTS = {"check": Part.CHECK, "pass": Part.PASS_ACTION, "decision": Part.DECISION, "told": Part.INSTRUCTION}


def told(published: typing.Mapping[str, typing.Any]) -> Rule:
    """What a stage is told: where it stands (the stages it holds at, its section), its words as one line."""
    stages = ", ".join(published["stages"]) or "every stage"
    where = " — ".join(w for w in (stages, published["section"]) if w)
    return Rule(
        RuleId(published["id"]), Part.INSTRUCTION, tuple(StageName(s) for s in published["stages"]),
        tuple(KindName(k) for k in published["kinds"]), Words(where), (), Words(""), Words(plain(published["told"])),
        (), Source(published["source"]), RuleState.RETIRED if published["retired"] else RuleState.ACTIVE,
        Source(published["placed"]))


def translated(published: typing.Mapping[str, typing.Any]) -> Rule:
    if published["part"] == "told":
        return told(published)
    return Rule(
        RuleId(published["id"]), PARTS[published["part"]],
        tuple(StageName(s) for s in published["stages"]), tuple(KindName(k) for k in published["kinds"]),
        Words(published["when"]),
        tuple(Outcome(OutcomeState(o["state"]), Words(o["said"]), tuple(StageName(t) for t in o.get("goes", ())))
              for o in published["outcomes"]),
        Words(published["why"]), Words(""), tuple(Words(r) for r in published["reports"]),
        Source(published["source"]), RuleState.RETIRED if published["retired"] else RuleState.ACTIVE,
        Source(published.get("bound", "")), Words(published.get("title", "")))


class DeliveryRules:
    """The rules the gate and the runner register, and the stage table — read once."""

    def rules(self) -> typing.Tuple[Rule, ...]:
        return tuple(translated(found) for found in pipeline_rules())

    def rows(self) -> typing.Tuple[StageRow, ...]:
        return tuple(StageRow(StageName(row["name"]), tuple(KindName(k) for k in row["kinds"]), GateTime(row["gate"]),
                              OrderPlace.IN_ORDER if row["in_order"] else OrderPlace.AFTER_ORDER, Words(row["window"]),
                              Words(row.get("about", "")), Source(row.get("source", "")))
                     for row in stage_rows())

    def orders(self) -> typing.Tuple[KindOrder, ...]:
        return tuple(KindOrder(KindName(kind), tuple(StageName(s) for s in stages))
                     for kind, stages in kind_orders().items())


class DeliveryFindings:
    """What the gate found over a story of the project <cwd>, as delivery publishes it."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def fired(self, story: str) -> typing.Tuple[Fired, ...]:
        found = story_gate_findings(self._cwd, story)["stages"]
        return tuple(Fired(StageName(stage), Words(item["check"]), OutcomeState(item["state"]))
                     for stage, items in found.items() for item in items)

    def refused(self, story: str) -> typing.Tuple[Refused, ...]:
        return tuple(Refused(Words(check), Count(times))
                     for check, times in story_gate_findings(self._cwd, story)["refused"].items())
