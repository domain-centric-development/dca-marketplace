"""What a stage is told for one story — its brief: the stage as the workflow has it, the told rules that hold for it and
the story's kind in the order the stage reads them, the gate rules it is measured by, the skills that carry its craft.
Decided over the workflow and the rules, never over a skill's text: the same story and stage give the same brief."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService, Value
from ..model.jump import RuleId
from ..model.stack_profile import SkillName
from ..model.stage import HandOver, StageName, StageText, StoryKind, Window
from ..model.workflow import Workflow
from ..model.workflow_rule import OutcomeState, RuleOrder, RulePart, RuleText, WorkflowRule


class CarrierRole(enum.Enum):
    """What a skill the profile names does for a stage."""

    CRAFT = "craft"          # the stage's craft (`carrier.<stage>`)
    GUARD = "guard"          # the guard over production code (`carrier.guard`)
    KNOWLEDGE = "knowledge"  # the method's knowledge, asked where in doubt (`knowledge`)


class Carrier(Value):
    role: CarrierRole
    skill: SkillName


class Told(Value):
    """One told rule as the stage reads it: its words under the section they stand in."""

    rule: RuleId
    section: typing.Optional[RuleText]
    words: RuleText


class Measure(Value):
    """A gate rule the stage's work is measured by: when it applies, and what a refusal by it says."""

    rule: RuleId
    when: RuleText
    refused: typing.Optional[RuleText]


class Brief(Value):
    stage: StageName
    kind: StoryKind
    about: typing.Optional[StageText]
    writes: typing.Optional[HandOver]
    window: typing.Optional[Window]
    told: typing.Tuple[Told, ...]
    measured: typing.Tuple[Measure, ...]
    carriers: typing.Tuple[Carrier, ...]


class StageBrief(DomainService):
    """The brief of a stage, over the stages of <workflow>."""

    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow

    def of(self, stage: StageName, kind: StoryKind, rules: typing.Sequence[WorkflowRule],
           measured_by: typing.Sequence[RuleId], carriers: typing.Sequence[Carrier]) -> Brief:
        """The brief of <stage> for a story of <kind>: the told rules of <rules> that hold there — every stage's
        first, then the stage's own, each in its skill's order —, the gate rules <measured_by> in their order."""
        found = self._workflow.stage(stage)
        if found is None:
            raise ValueError(f"the workflow has no stage {stage.value}")
        if kind not in found.kinds:
            raise ValueError(f"a {kind.value} story does not run the {stage.value} stage")
        told = sorted((r for r in rules if r.part is RulePart.TOLD and r.retired is None and r.told is not None
                       and holds(r, stage, kind)),
                      key=lambda r: (1 if r.stages else 0, common_place(r).value, r.marked.value if r.marked else "",
                                     r.order.value if r.order else 0, r.id.value))
        by_id = {r.id: r for r in rules}
        measured = [by_id[rule_id] for rule_id in measured_by if rule_id in by_id]
        return Brief(stage, kind, found.about, found.hand_over, found.window,
                     tuple(Told(r.id, r.section, r.told) for r in told if r.told is not None),
                     tuple(Measure(r.id, r.when, refused_by(r)) for r in measured
                           if r.retired is None and holds(r, stage, kind)),
                     tuple(carriers))


def holds(rule: WorkflowRule, stage: StageName, kind: StoryKind) -> bool:
    """A rule holds at <stage> for <kind> unless it names other stages or other kinds."""
    return (not rule.stages or stage in rule.stages) and (not rule.kinds or kind in rule.kinds)


#: Where every stage's rules stand, first to last: what every stage holds to, then the files it hands over.
EVERY_STAGE = ("stage-common.md", "file-contracts.md")


def common_place(rule: WorkflowRule) -> RuleOrder:
    """Every stage's rules before the stage's own; among them, what every stage holds to before the files it hands
    over — within, the text that carries them and their place in it."""
    carried = rule.marked.value if rule.marked else ""
    return RuleOrder(next((i for i, name in enumerate(EVERY_STAGE, 1) if carried.endswith(name)),
                          len(EVERY_STAGE) + 1))


def refused_by(rule: WorkflowRule) -> typing.Optional[RuleText]:
    return next((o.said for o in rule.outcomes if o.state is OutcomeState.FAIL), None)
