"""The workflow a story runs through: its stages in their order — what each one writes, which process may carry it,
which stories run it, what its gate holds it to — loaded from the workflow's repository, validated as a whole. Every
question about a stage is the workflow's; nothing else names a stage to decide on it."""

from __future__ import annotations

import re
import typing

from ....building_blocks import AggregateRoot, DomainException, Id
from .journal_marks import JournalMarks, MarkKind, MarkName, Seq
from .jump import AGAIN, Jump, Next, RuleId, STOP, Target
from .route import Around, Move, REVIEWED_KINDS, RouteStep, SKIP_REASONS
from .stage import HandOver, Role, Stage, StageName, StageText, StoryKind, Trait, Window
from .story_state import Detail, HandOverText
from .workflow_rule import Written

WORKFLOW_NAME = re.compile(r"[a-z][a-z0-9-]*")


class WorkflowName(Id):
    """A workflow by its name — `delivery`, the one every story runs today."""

    value: str

    def __post_init__(self) -> None:
        if not WORKFLOW_NAME.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no workflow name")


#: The workflow every story runs.
DELIVERY = WorkflowName("delivery")


class InconsistentWorkflow(DomainException):
    """The stage files do not make one workflow: a stage named twice or after a target, a hand-over written twice or
    weighed but never written, a role given twice."""


class MissingRole(DomainException):
    """The factory asked for a stage by its role, and no stage of the workflow plays it."""

    def __init__(self, name: WorkflowName, role: Role) -> None:
        super().__init__(f"workflow {name.value}: no stage is `role: {role.value}`")
        self.role = role


class Workflow(AggregateRoot[WorkflowName]):
    """The stages in their order: each name once, each hand-over written by one stage, each hand-over a gate weighs
    written by a stage of it. Where each stage is written, as a person finds it, where the repository says."""

    def __init__(self, name: WorkflowName, stages: typing.Sequence[Stage],
                 written: typing.Optional[typing.Mapping[StageName, Written]] = None,
                 every_stage: typing.Optional[StageText] = None) -> None:
        super().__init__()
        names = [s.name.value for s in stages]
        if not names:
            raise InconsistentWorkflow(f"workflow {name.value}: has no stage")
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise InconsistentWorkflow(f"workflow {name.value}: names the stage {', '.join(twice)} twice")
        reserved = [n for n in names if n in (AGAIN, STOP)]
        if reserved:
            raise InconsistentWorkflow(f"workflow {name.value}: a stage named {', '.join(reserved)} — a target, "
                                       f"not a stage")
        files = [s.hand_over.value for s in stages if s.hand_over is not None]
        shared = sorted({f for f in files if files.count(f) > 1})
        if shared:
            raise InconsistentWorkflow(f"workflow {name.value}: several stages write {', '.join(shared)}")
        unwritten = sorted({h.value for s in stages for h in s.sizes} - set(files))
        if unwritten:
            raise InconsistentWorkflow(f"workflow {name.value}: a gate weighs {', '.join(unwritten)}, which no "
                                       f"stage writes")
        roles = [s.role.value for s in stages if s.role is not None]
        given_twice = sorted({r for r in roles if roles.count(r) > 1})
        if given_twice:
            raise InconsistentWorkflow(f"workflow {name.value}: several stages are `role: {', '.join(given_twice)}`")
        self._id = name
        self._stages = tuple(stages)
        self._written = dict(written or {})
        self._every_stage = every_stage

    @classmethod
    def restore(cls, name: WorkflowName, stages: typing.Sequence[Stage],
                written: typing.Optional[typing.Mapping[StageName, Written]] = None,
                every_stage: typing.Optional[StageText] = None) -> Workflow:
        """The workflow as it was kept — the one way a repository builds it."""
        return cls(name, stages, written, every_stage)

    @property
    def id(self) -> WorkflowName:
        return self._id

    def role(self, role: Role) -> StageName:
        """The stage that plays <role>; MissingRole where none does."""
        found = next((s.name for s in self._stages if s.role is role), None)
        if found is None:
            raise MissingRole(self._id, role)
        return found

    @property
    def stages(self) -> typing.Tuple[Stage, ...]:
        """Every stage, in the workflow's order — the run order's steps first, the steps after it last."""
        return self._stages

    def stage(self, name: StageName) -> typing.Optional[Stage]:
        """The stage by its name, None for a name the workflow has no stage of."""
        return next((s for s in self._stages if s.name == name), None)

    @property
    def every_stage(self) -> typing.Optional[StageText]:
        """What every stage is told before its own — a frame like a stage's, its rules by marker."""
        return self._every_stage

    def written(self, name: StageName) -> typing.Optional[Written]:
        """Where the stage is written — `workflow/stages/plan.md` —, None where the repository says nothing."""
        return self._written.get(name)

    def having(self, trait: Trait) -> typing.Tuple[Stage, ...]:
        return tuple(s for s in self._stages if trait in s.traits)

    def without(self, trait: Trait) -> typing.Tuple[Stage, ...]:
        return tuple(s for s in self._stages if trait not in s.traits)

    def in_window(self, window: Window) -> typing.Tuple[Stage, ...]:
        """The stages the shared <window> may carry, in order."""
        return tuple(s for s in self._stages if s.window is window)

    def order(self, kind: StoryKind) -> typing.Tuple[StageName, ...]:
        """The run order of a story of <kind>."""
        return tuple(s.name for s in self._stages if Trait.IN_ORDER in s.traits and kind in s.kinds)

    def briefed_at(self, name: StageName, kind: StoryKind) -> typing.Tuple[Stage, ...]:
        """The stages whose hand-over the gate after <name> holds to its brief, for a story of <kind>: <name> and the
        stages before it in the run order no gate after them checks — back to the one before that a gate checks after
        it. None where no gate runs after <name>."""
        found = self.stage(name)
        if found is None or Trait.POST_GATED not in found.traits:
            return ()
        order = [s for s in self._stages if Trait.IN_ORDER in s.traits and kind in s.kinds]
        if found not in order:
            return (found,) if found.hand_over else ()
        held = [found]
        for earlier in reversed(order[:order.index(found)]):
            if Trait.POST_GATED in earlier.traits:
                break
            held.insert(0, earlier)
        return tuple(s for s in held if s.hand_over is not None)

    def hand_over(self, name: StageName) -> typing.Optional[HandOver]:
        """The file the stage writes, None for a stage that writes none."""
        found = self.stage(name)
        return found.hand_over if found is not None else None

    # --- the current pass: a stage run again makes every later hand-over an earlier pass's, read from the journal's
    # order, never from file times

    def written_at(self, marks: JournalMarks, stage: StageName) -> typing.Optional[Seq]:
        """When the stage's file last held for the pass: its last write, or for a stage gated after its file a later
        pass (or hold) of its own gate; None where the file was marked an earlier pass's since."""
        row = self.stage(stage)
        if row is None or row.hand_over is None:
            return None
        name = MarkName(row.hand_over.value)
        at = marks.at(MarkKind.WROTE, name).value
        if Trait.POST_GATED in row.traits:
            gate = MarkName(stage.value)
            at = max(at, marks.at(MarkKind.PASS, gate).value, marks.at(MarkKind.HELD, gate).value)
        outdated = marks.has(MarkKind.OUTDATED, name)
        return None if outdated is not None and outdated.value > at else Seq(at)

    def holding(self, marks: JournalMarks, order: typing.Sequence[StageName],
                present: typing.AbstractSet[StageName]) -> typing.Tuple[StageName, ...]:
        """The stages, in run order, whose file on disk holds for the current pass: up to the first that is older
        than one before it — a stage that ran again ended the pass the later files were written in. A stage whose
        gate passed after the file before it was written holds, though its own file is older."""
        holding: typing.List[StageName] = []
        newest: typing.Optional[int] = None
        for stage in order:
            if stage not in present:
                continue
            written = self.written_at(marks, stage)
            if written is None or (newest is not None and written.value < newest):
                break
            holding.append(stage)
            newest = max(written.value, newest or 0)
        return tuple(holding)

    # --- a story's route: which stage runs how from where it starts, and where it goes once a gate, a stage or the
    # judge sent it back — decided over the stages and what the run says, never over a file

    def steps(self, kind: StoryKind, start: StageName, shared: typing.FrozenSet[Window]) -> typing.Tuple[RouteStep, ...]:
        """The stages from <start> on in the run order, each with how it runs: skipped where the kind does not run it,
        the builder's stages in one process where it is shared, the verifier's likewise — the route ends with it."""
        steps: typing.List[RouteStep] = []
        started, built = False, False
        for stage in self.having(Trait.IN_ORDER):
            started = started or stage.name == start
            if not started:
                continue
            carried = Window.BUILDER in shared and stage.window is Window.BUILDER
            around = {Around.PAUSE} if stage.name == start or not carried else set()
            if kind not in stage.kinds:
                why = SKIP_REASONS.get(kind, f"a {kind.value} story does not run it")
                steps.append(RouteStep(stage.name, Move.SKIP, frozenset(around), Detail(why)))
                continue
            if Trait.GATED in stage.traits and Trait.POST_GATED not in stage.traits:
                around.add(Around.GATE_BEFORE)
            if carried:
                steps.append(RouteStep(stage.name, Move.CARRIED if built else Move.BUILDER, frozenset(around)))
                built = True
                continue
            if stage.role is Role.JUDGES and kind in REVIEWED_KINDS:
                around.add(Around.REVIEWS)
            if Window.VERIFIER in shared and stage.window is Window.VERIFIER:
                steps.append(RouteStep(stage.name, Move.VERIFIER, frozenset(around)))
                break
            if Trait.POST_GATED in stage.traits:
                around.add(Around.GATE_AFTER)
            if stage.role is Role.JUDGES:
                around.add(Around.VERDICT)
            steps.append(RouteStep(stage.name, Move.STAGE, frozenset(around)))
        return tuple(steps)

    def applying(self, asked: StageName, applies: StageName) -> StageName:
        """The stage that applies an answer: the one the answer names (`applies: test` — an answer that changes a
        test goes back to the test stage, whoever asked), else the stage that asked."""
        return applies if applies in self.order(StoryKind.STORY) else asked

    def resumes_at(self, asked: StageName, applies: StageName) -> StageName:
        """Where the story resumes for an answer: the earlier of the stage that asked and the one the answer names.
        A plan's question answered `applies: test` still re-plans — the plan lists the tests that change — and the
        test stage after it takes the changed expectation."""
        order = self.order(StoryKind.STORY)
        named = self.applying(asked, applies)
        if asked not in order:
            return named
        return min((asked, named), key=lambda stage: order.index(stage) if stage in order else len(order))

    def window(self, kind: StoryKind, window: Window, start: typing.Optional[StageName] = None) -> typing.Tuple[StageName, ...]:
        """The stages a shared window carries for the kind — from <start> on where one is named."""
        carried, on = [], start is None
        for stage in self.in_window(window):
            on = on or stage.name == start
            if on and kind in stage.kinds:
                carried.append(stage.name)
        return tuple(carried)

    def red_check(self, kind: StoryKind, start: StageName, jump: Jump) -> typing.Optional[Next]:
        """Where a story that starts at <start> goes when its red proof went stale — where <jump> sends it, the stage
        that records the proof again — or None where the start does not rest on it: a stage that lists no files, the
        red stage itself, a kind that runs no tests."""
        found = self.stage(start)
        if found is None or Trait.LISTS not in found.traits or Trait.RED in found.traits:
            return None
        named = self.stage(StageName(jump.targets[0].value)) if jump.targets else None
        if named is not None and kind not in named.kinds:
            return None
        return self.jump(kind, start, jump)

    def jump(self, kind: StoryKind, here: StageName, jump: Jump) -> Next:
        """Where a rule with one way sends the story from <here>: its first target — `again` where it names none."""
        return self._to(kind, here, jump.targets[0] if jump.targets else Target(AGAIN), jump.rule)

    def chosen(self, kind: StoryKind, here: StageName, jump: Jump, chosen: Target) -> Next:
        """A target the run's facts chose among the rule's ways (the judge's `back:`): taken where the rule names it;
        one it does not name stops the run — the rule, not the run, says where a story may go."""
        if chosen not in jump.targets:
            return Next(None, jump.rule)
        return self._to(kind, here, chosen, jump.rule)

    def after_refusal(self, kind: StoryKind, refused: StageName, resumes: typing.Optional[StageName],
                      jumps: typing.Sequence[Jump], fallback: RuleId) -> Next:
        """Where a refused gate sends the story — by the rules that failed: a rule whose one way is `stop` ends the
        run; else the earliest stage any of them names, or the refused stage (or the earlier one the story's state
        resumes at, the <fallback> rule's way) — an earlier stage covers the later ones."""
        stopping = next((j for j in jumps if j.targets == (Target(STOP),)), None)
        if stopping is not None:
            return Next(None, stopping.rule)
        ways = [self._to(kind, refused, target, j.rule)
                for j in jumps for target in (j.targets or (Target(AGAIN),)) if target != Target(STOP)]
        ways.append(Next(self.again_from(refused, resumes), fallback))
        order = self.order(kind)
        return min(ways, key=lambda way: order.index(way.stage) if way.stage in order else len(order))

    def _to(self, kind: StoryKind, here: StageName, target: Target, rule: RuleId) -> Next:
        if target == Target(STOP):
            return Next(None, rule)
        if target == Target(AGAIN):
            return Next(here, rule)
        return Next(self.back_for(kind, StageName(target.value)), rule)

    def again_from(self, refused: StageName, resumes: typing.Optional[StageName]) -> StageName:
        """The stage a refused gate's round starts at: the refused stage, or an earlier one the story's state resumes
        at — whose file it reads as an earlier pass's."""
        for stage in (s.name for s in self.having(Trait.IN_ORDER)):
            if stage == refused:
                break
            if stage == resumes:
                return stage
        return refused

    def judged_back(self, kind: StoryKind, judge: HandOverText) -> StageName:
        """Where the judge's `changes-requested` sends the story: `back: test` — a confirmed defect is in a test, which
        only the test stage may change — to the test stage, anything else to the build; for a kind without that
        stage, the builder stage before it (`back_for`)."""
        for line in judge.value.splitlines():
            if line.strip().lower().startswith("back:"):
                named = line.split(":", 1)[1].strip().strip("`\"' ").lower()
                tests = self.role(Role.TESTS)
                return self.back_for(kind, tests if named == tests.value else self.role(Role.BUILDS))
        return self.back_for(kind, self.role(Role.BUILDS))

    def back_for(self, kind: StoryKind, stage: StageName) -> StageName:
        """Where a round goes back to: <stage>, or the last builder stage before it the kind runs."""
        found = self.stage(stage)
        if found is not None and kind in found.kinds:
            return stage
        back = stage
        for builder in self.in_window(Window.BUILDER):
            if kind in builder.kinds:
                back = builder.name
            if builder.name == stage:
                break
        return back

    def targets(self) -> typing.FrozenSet[Target]:
        """Every target a rule's outcome may send a story to: a stage of the workflow, `again`, `stop`."""
        return frozenset(Target(name) for name in [s.name.value for s in self._stages] + [AGAIN, STOP])
