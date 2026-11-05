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
from ..model.stage_story import Place
from ..model.workflow import Workflow
from ..model.workflow_rule import OutcomeState, RulePart, RuleText, WorkflowRule


class CarrierRole(enum.Enum):
    """What a skill the profile names does for a stage."""

    CRAFT = "craft"          # the stage's craft (`carrier.<stage>`)
    GUARD = "guard"          # the guard over production code (`carrier.guard`)
    FRONTEND = "frontend"    # the frontend craft over pages, templates, stylesheets and client scripts (`carrier.frontend`)
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
    #: what every stage is told, as it reads it: every stage's frame, each rule's words where its marker stands — a rule
    #: that does not hold for the kind left out, a section left without any rule left out whole —, then the told rules
    #: of every stage no frame places
    common: StageText
    #: what this stage is told beyond it, read the same way: its own frame, then its own told rules no frame places
    own: StageText
    told: typing.Tuple[Told, ...]
    measured: typing.Tuple[Measure, ...]
    carriers: typing.Tuple[Carrier, ...]

    @property
    def said(self) -> StageText:
        """All the stage is told: what every stage is, then its own."""
        return StageText("\n\n".join(p.value for p in (self.common, self.own) if p.value.strip()))


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
        framed = [expanded(frame, held, placed) if frame is not None else None
                  for frame in (self._workflow.every_stage, found.frame)]
        in_frames = {rule_id for done in framed if done is not None for rule_id in done[1]}
        rest = sorted((r for r in held.values() if r.id not in in_frames and not placed_in(r, self._workflow, found)),
                      key=lambda r: (r.see.value if r.see else "", r.order.value if r.order else 0, r.id.value))
        common: typing.List[str] = []
        own: typing.List[str] = []
        order: typing.List[RuleId] = []
        for done, parts, rules_of in ((framed[0], common, [r for r in rest if not r.stages]),
                                      (framed[1], own, [r for r in rest if r.stages])):
            if done is not None:
                parts.append(done[0].value)
                order += done[1]
            if rules_of:
                parts.append("\n\n".join(rest_text(r).value for r in rules_of))
                order += [r.id for r in rules_of]
        by_id = {r.id: r for r in rules}
        measured = [by_id[rule_id] for rule_id in measured_by if rule_id in by_id]
        return Brief(stage, kind, found.about, found.hand_over, found.window,
                     StageText("\n\n".join(p for p in common if p.strip())),
                     StageText("\n\n".join(p for p in own if p.strip())),
                     tuple(Told(held[i].id, held[i].section, held[i].told or RuleText("")) for i in order
                           if i in held),
                     tuple(Measure(r.id, r.when, refused_by(r)) for r in measured
                           if r.retired is None and holds(r, stage, kind)),
                     tuple(carriers))

    def every_stage(self, rules: typing.Sequence[WorkflowRule]) -> StageText:
        """What every stage is told, for a session that works no stage — a request: every stage's frame with the told
        rules of <rules> that name no stage and no kind, then those no frame places."""
        held = {r.id: r for r in rules if r.part is RulePart.TOLD and r.retired is None and r.told is not None
                and not r.stages and not r.kinds}
        placed = {r.id for r in rules if r.part is RulePart.TOLD}
        frame = self._workflow.every_stage
        parts: typing.List[str] = []
        used: typing.Tuple[RuleId, ...] = ()
        if frame is not None:
            text, used = expanded(frame, held, placed)
            parts.append(text.value)
        rest = sorted((r for r in held.values() if r.id not in used),
                      key=lambda r: (r.see.value if r.see else "", r.order.value if r.order else 0, r.id.value))
        if rest:
            parts.append("\n\n".join(rest_text(r).value for r in rest))
        return StageText("\n\n".join(p for p in parts if p.strip()))


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
    where = rule.see.value if rule.see else ""
    head = f"### {rule.section.value}\n\n" if rule.section else ""
    more = f"\n\n(The rest of it: `{where}`.)" if where else ""
    return StageText(f"{head}<!-- rule: {rule.id.value} -->\n{rule.told.value if rule.told else ''}{more}")


def holds(rule: WorkflowRule, stage: StageName, kind: StoryKind) -> bool:
    """A rule holds at <stage> for <kind> unless it names other stages or other kinds."""
    return (not rule.stages or stage in rule.stages) and (not rule.kinds or kind in rule.kinds)


def written(brief: Brief, told: StageText, every_stage: typing.Optional[Place] = None) -> StageText:
    """<brief> in the order a stage works it: what the stage is, the skills it loads, what it is told (<told> — all of
    it, or its own part after a pointer to <every_stage>, what every stage is told) and what its gate holds it to."""
    lines = [f"# The {brief.stage.value} stage — a {brief.kind.value}", ""]
    if brief.about:
        lines += [brief.about.value, ""]
    if brief.writes:
        lines += [f"It writes `{brief.writes.value}`" + (f", carried by the shared {brief.window.value}"
                                                         if brief.window else "") + ".", ""]
    if every_stage:
        lines += [f"What every stage is told stands in `{every_stage.value}`: read it before this brief.", ""]
    if brief.carriers:
        lines += ["## The skills you load", ""]
        lines += [f"- {c.role.value}: the `{c.skill.value}` skill" for c in brief.carriers]
        lines.append("")
    lines += ["## What you do", "", told.value, ""]
    if brief.measured:
        lines += ["## What the gate holds you to", ""]
        lines += [f"- `{m.rule.value}` — when: {m.when.value}" + (f"; refused: {m.refused.value}" if m.refused else "")
                  for m in brief.measured]
        lines.append("")
    return StageText("\n".join(lines).rstrip("\n") + "\n")


def refused_by(rule: WorkflowRule) -> typing.Optional[RuleText]:
    return next((o.said for o in rule.outcomes if o.state is OutcomeState.FAIL), None)
