"""What a stage is told for one story — its brief: the stage as the workflow has it, the told rules that hold for it and
the story's kind in the order the stage reads them, the gate rules it is measured by, the skills that carry its craft.
Decided over the workflow and the rules, never over a skill's text: the same story and stage give the same brief."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import DomainService, Value
from ..model.jump import RuleId
from ..model.stack_profile import SkillName
from ..model.stage import HandOver, Stage, StageName, StageText, StoryKind, Window
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
    #: what the stage is told, as it reads it: every stage's frame, then its own, each rule's words where its marker
    #: stands — a rule that does not hold for the kind left out, a section left without any rule left out whole
    said: StageText
    told: typing.Tuple[Told, ...]
    measured: typing.Tuple[Measure, ...]
    carriers: typing.Tuple[Carrier, ...]


class StageBrief(DomainService):
    """The brief of a stage, over the stages of <workflow>."""

    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow

    def of(self, stage: StageName, kind: StoryKind, rules: typing.Sequence[WorkflowRule],
           measured_by: typing.Sequence[RuleId], carriers: typing.Sequence[Carrier]) -> Brief:
        """The brief of <stage> for a story of <kind>: the frames with the told rules of <rules> that hold there, a
        told rule no frame places after them, the gate rules <measured_by> in their order."""
        found = self._workflow.stage(stage)
        if found is None:
            raise ValueError(f"the workflow has no stage {stage.value}")
        if kind not in found.kinds:
            raise ValueError(f"a {kind.value} story does not run the {stage.value} stage")
        held = {r.id: r for r in rules if r.part is RulePart.TOLD and r.retired is None and r.told is not None
                and holds(r, stage, kind)}
        placed = {r.id for r in rules if r.part is RulePart.TOLD}
        parts: typing.List[str] = []
        order: typing.List[RuleId] = []
        for frame in (self._workflow.every_stage, found.frame):
            if frame is not None:
                text, used = expanded(frame, held, placed)
                parts.append(text.value)
                order += used
        rest = sorted((r for r in held.values() if r.id not in order and not placed_in(r, self._workflow, found)),
                      key=lambda r: (1 if r.stages else 0, common_place(r).value,
                                     r.marked.value if r.marked else "", r.order.value if r.order else 0, r.id.value))
        if rest:
            parts.append("\n\n".join(rest_text(r).value for r in rest))
            order += [r.id for r in rest]
        by_id = {r.id: r for r in rules}
        measured = [by_id[rule_id] for rule_id in measured_by if rule_id in by_id]
        return Brief(stage, kind, found.about, found.hand_over, found.window,
                     StageText("\n\n".join(p for p in parts if p.strip())),
                     tuple(Told(held[i].id, held[i].section, held[i].told or RuleText("")) for i in order
                           if i in held),
                     tuple(Measure(r.id, r.when, refused_by(r)) for r in measured
                           if r.retired is None and holds(r, stage, kind)),
                     tuple(carriers))


MARKER = re.compile(r"^\s*<!--\s*rule:\s*(\S+)\s*-->\s*$")
HEADING = re.compile(r"^(#{1,6})\s")


def expanded(frame: StageText, held: typing.Mapping[RuleId, WorkflowRule],
             placed: typing.AbstractSet[RuleId]) -> typing.Tuple[StageText, typing.Tuple[RuleId, ...]]:
    """<frame> with each marker's rule words in place where the rule holds (<held>), left out where it does not, and
    every section whose rules all were left out left out whole — a section with no rule stays as it is."""
    blocks: typing.List[typing.Tuple[int, typing.List[str]]] = [(0, [])]
    fenced = False
    for line in frame.value.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        heading = HEADING.match(line) if not fenced else None
        if heading:
            blocks.append((len(heading.group(1)), [line]))
        else:
            blocks[-1][1].append(line)
    out: typing.List[str] = []
    used: typing.List[RuleId] = []
    dropping: typing.Optional[int] = None
    for level, lines in blocks:
        if dropping is not None and level and level <= dropping:
            dropping = None
        if dropping is not None:
            continue
        marked = [RuleId(m.group(1)) for m in (MARKER.match(line) for line in lines) if m]
        kept = [rule_id for rule_id in marked if rule_id in held]
        if marked and not kept and level:
            dropping = level
            continue
        for line in lines:
            mark = MARKER.match(line)
            if mark is None:
                out.append(line)
                continue
            rule_id = RuleId(mark.group(1))
            if rule_id in held:
                told = held[rule_id].told
                out += [line, told.value if told is not None else ""]
                used.append(rule_id)
            elif rule_id not in placed:
                out.append(line)
    return StageText("\n".join(out).strip("\n")), tuple(used)


def placed_in(rule: WorkflowRule, workflow: Workflow, stage: Stage) -> bool:
    """Whether a frame of <workflow> places <rule> — at <stage> or everywhere."""
    marker = f"<!-- rule: {rule.id.value} -->"
    frames = [workflow.every_stage, stage.frame]
    return any(f is not None and marker in f.value for f in frames)


def rest_text(rule: WorkflowRule) -> StageText:
    """A told rule no frame places: its words under its section, and where the rest of it stands."""
    where = rule.marked.value if rule.marked else ""
    head = f"### {rule.section.value}\n\n" if rule.section else ""
    more = f"\n\n(The rest of it: `{where}`.)" if where else ""
    return StageText(f"{head}<!-- rule: {rule.id.value} -->\n{rule.told.value if rule.told else ''}{more}")


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
