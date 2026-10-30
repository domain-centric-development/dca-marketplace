"""Delivery's rules, asked through delivery's open host service and translated into the rulebook's model."""

from __future__ import annotations

import typing

from .....delivery.api.rules import kind_orders, pipeline_rules, stage_rows
from ....domain.model.rule import (
    KindName, Outcome, OutcomeState, Part, Rule, RuleId, RuleState, Source, StageName, Words)
from ....domain.model.rulebook import GateTime, KindOrder, OrderPlace, StageRow

#: How delivery publishes where a rule sits, in the rulebook's terms.
PARTS = {"check": Part.CHECK, "pass": Part.PASS_ACTION, "decision": Part.DECISION}


def translated(published: typing.Mapping[str, typing.Any]) -> Rule:
    return Rule(
        RuleId(published["id"]), PARTS[published["part"]],
        tuple(StageName(s) for s in published["stages"]), tuple(KindName(k) for k in published["kinds"]),
        Words(published["when"]),
        tuple(Outcome(OutcomeState(o["state"]), Words(o["said"])) for o in published["outcomes"]),
        Words(published["why"]), Words(""), tuple(Words(r) for r in published["reports"]),
        Source(published["source"]), RuleState.RETIRED if published["retired"] else RuleState.ACTIVE)


class DeliveryRules:
    """The rules the gate and the runner register, and the stage table — read once."""

    def rules(self) -> typing.Tuple[Rule, ...]:
        return tuple(translated(found) for found in pipeline_rules())

    def rows(self) -> typing.Tuple[StageRow, ...]:
        return tuple(StageRow(StageName(row["name"]), tuple(KindName(k) for k in row["kinds"]), GateTime(row["gate"]),
                              OrderPlace.IN_ORDER if row["in_order"] else OrderPlace.AFTER_ORDER, Words(row["window"]))
                     for row in stage_rows())

    def orders(self) -> typing.Tuple[KindOrder, ...]:
        return tuple(KindOrder(KindName(kind), tuple(StageName(s) for s in stages))
                     for kind, stages in kind_orders().items())
