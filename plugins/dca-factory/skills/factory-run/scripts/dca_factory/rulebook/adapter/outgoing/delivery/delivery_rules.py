"""Delivery's rules, asked through delivery's open host service and translated into the rulebook's model."""

from __future__ import annotations

import typing

from .....delivery.api.rules import (
    kind_orders, pipeline_rules, project_runs, round_limit, stage_rows, story_gate_findings)
from ....domain.model.rule import (
    Count, Fired, KindName, Outcome, OutcomeState, Part, Refused, Restart, Rule, RuleId, RuleState, Source, StageName,
    Words)
from ....domain.model.rule import Moment
from ....domain.model.rulebook import GateTime, KindOrder, OrderPlace, StageRow
from ....domain.model.runs import GateHand, JournalLine, JournalLineKind, StoryJournal
from ..skills.skill_files import plain
from ....application.shared.decided_rules import DecidedRules
from ....application.shared.gate_findings import GateFindings
from ....application.shared.project_journals import ProjectJournals

#: How delivery publishes where a rule sits, in the rulebook's terms.
PARTS = {"check": Part.CHECK, "pass": Part.PASS_ACTION, "decision": Part.DECISION, "told": Part.INSTRUCTION}


def told(published: typing.Mapping[str, typing.Any]) -> Rule:
    """What a stage is told: where it stands (the stages it holds at, its section), its words as one line."""
    stages = ", ".join(published["stages"]) or "every stage"
    where = " — ".join(w for w in (stages, published["section"]) if w)
    return Rule(
        RuleId(published["id"]), Part.INSTRUCTION, tuple(StageName(s) for s in published["stages"]),
        tuple(KindName(k) for k in published["kinds"]), Words(where), (), Words(published.get("why", "")),
        Words(plain(published["told"])),
        (), Source(published["source"]), RuleState.RETIRED if published["retired"] else RuleState.ACTIVE,
        Source(published["placed"]), restart=restart_of(published))


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
        Source(published.get("bound", "")), Words(published.get("title", "")), restart_of(published))


def restart_of(published: typing.Mapping[str, typing.Any]) -> typing.Optional[Restart]:
    restart = published.get("restart")
    return Restart(StageName(restart["stage"]), Words(restart["when"])) if restart else None


class DeliveryRules(DecidedRules):
    """The rules the gate and the runner register, and the stage table — read once."""

    def rules(self) -> typing.Tuple[Rule, ...]:
        return tuple(translated(found) for found in pipeline_rules())

    def rows(self) -> typing.Tuple[StageRow, ...]:
        return tuple(StageRow(StageName(row["name"]), tuple(KindName(k) for k in row["kinds"]), GateTime(row["gate"]),
                              OrderPlace.IN_ORDER if row["in_order"] else OrderPlace.AFTER_ORDER, Words(row["window"]),
                              Words(row.get("about", "")), Source(row.get("source", "")))
                     for row in stage_rows())

    def round_limit(self) -> Count:
        return Count(round_limit())

    def orders(self) -> typing.Tuple[KindOrder, ...]:
        return tuple(KindOrder(KindName(kind), tuple(StageName(s) for s in stages))
                     for kind, stages in kind_orders().items())


class DeliveryFindings(GateFindings):
    """What the gate found over a story of the project <cwd>, as delivery publishes it."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def fired(self, story: str) -> typing.Tuple[Fired, ...]:
        found = story_gate_findings(self._cwd, story)["stages"]
        return tuple(Fired(StageName(stage), Words(item["check"]), OutcomeState(item["state"]))
                     for stage, items in found.items() for item in items)

    def refused(self, story: str) -> typing.Tuple[Refused, ...]:
        found = story_gate_findings(self._cwd, story)
        return tuple(Refused(Words(check), Count(times), StageName(stage))
                     for stage, checks in found.get("refused_at", {}).items() for check, times in checks.items())


#: A journal line's kind, in the rulebook's terms — a domain event only where it took a delivered story back.
EVENT_KINDS = {"gate": JournalLineKind.GATE, "jump": JournalLineKind.JUMP, "restart": JournalLineKind.RESTART,
               "stage-start": JournalLineKind.START, "rounds-reset": JournalLineKind.FROM}
REOPENED = "StoryReopened"


def run_event(line: typing.Mapping[str, typing.Any]) -> typing.Optional[JournalLine]:
    """One journal line as the reading takes it; None for a line it does not read."""
    kind, fields, at = line["kind"], line["fields"], Moment(line["at"])
    if kind == "event":
        return JournalLine(JournalLineKind.REOPENED, at, StageName("plan")) if line["name"] == REOPENED else None
    if kind not in EVENT_KINDS:
        return None
    if kind == "gate":
        code = fields.get("exit", "")
        if code not in ("0", "1"):
            return None                         # a gate that waits for a person (3) or broke (2) refused nothing
        refused = code == "1"
        checks = tuple(Words(c) for c in fields.get("fail", "").split(",") if c)
        return JournalLine(JournalLineKind.GATE, at, StageName(line["name"]),
                        state=OutcomeState.FAIL if refused else OutcomeState.PASS,
                        hand=GateHand.RUNNER if fields.get("by", "runner") == "runner" else GateHand.STAGE,
                        checks=checks)
    if kind == "jump":
        return JournalLine(JournalLineKind.JUMP, at, StageName(line["name"]), source=StageName(fields.get("from", "")),
                        rule=Words(fields.get("rule", "")))
    if kind == "restart":
        return JournalLine(JournalLineKind.RESTART, at, StageName(line["name"]), rule=Words(fields.get("rule", "")),
                        reason=Words(fields.get("reason", "")))
    return JournalLine(EVENT_KINDS[kind], at, StageName(line["name"]))


class DeliveryJournals(ProjectJournals):
    """The stories' journals of the project <cwd>, as delivery publishes them."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def journals(self) -> typing.Tuple[StoryJournal, ...]:
        kinds = {k.value: k for k in KindName}
        found = []
        for run in project_runs(self._cwd):
            events = tuple(e for e in (run_event(line) for line in run["events"]) if e is not None)
            found.append(StoryJournal(Words(run["story"]), kinds.get(run["kind"]), events))
        return tuple(found)
