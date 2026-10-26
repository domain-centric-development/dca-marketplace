"""Run a story: its stages from where it starts, a gate between them, a round back where a gate, the build stage or the
judge sends it, and its integration once it is delivered — the route decided by `StoryRoute`, every step taken
through the port."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.stage import StageName, StoryKind, Trait, Window
from ...domain.service.story_route import Around, Judged, Move, row, StoryRoute
from ..shared.run_lines import RunLines
from ..shared.story_stages import StoryStages

PLAN, TEST, BUILD, TIDY = StageName("plan"), StageName("test"), StageName("build"), StageName("tidy")
JUDGE, DOCUMENT, ADOPT, INTEGRATE = StageName("judge"), StageName("document"), StageName("adopt"), StageName("integrate")

#: What one pass of the route ends with: the run's exit, or the stage a round runs the story again from.
Ended = typing.Union[int, StageName]


@dataclasses.dataclass(frozen=True)
class RunStoryCommand:
    story: str
    start: typing.Optional[str] = None
    dry: bool = False
    gate_first: bool = False                            #: a resumed stage whose file exists is gated before it runs
    shared: typing.FrozenSet[Window] = frozenset()      #: the windows that carry their stages in one process


class RunStoryInputPort(UseCase[RunStoryCommand, int], typing.Protocol):
    """Run a story: its exit."""


class RunStoryUseCase:
    """The story's stages, round after round: 0 when it ran through, 3 when it waits for a person, 1 when it failed
    or the rounds did not converge, 4 at a limit, 5 when the checkout was taken over, 7 when a person's file changed
    under a stage."""

    def __init__(self, stages: StoryStages, lines: RunLines) -> None:
        self._stages = stages
        self._lines = lines
        self._gate_first = False

    def execute(self, command: RunStoryCommand) -> int:
        self._gate_first = command.gate_first
        start = StageName(command.start or PLAN.value)
        while True:
            ended = self._route(command, start)
            if isinstance(ended, StageName):
                start = ended
                continue
            return ended

    def _route(self, command: RunStoryCommand, start: StageName) -> Ended:
        """One pass from <start> on."""
        story, dry = command.story, command.dry
        waiting = self._stages.open_decisions(story)
        if waiting:
            self._lines.err(f"factory: story {story} waits for a decision — no stage runs until it is answered:")
            for record in waiting:
                self._lines.err(f"factory:   {record}")
            self._lines.err("factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that "
                            "asked (--from <stage>).")
            return 3
        kind = self._stages.kind(story)
        # Every gate passed in the story's worktree: only the integration is left, and it delivers the story; an
        # adopted story whose judge passed: only the adopt gate.
        if start == INTEGRATE:
            return self._integrate(command)
        if start == ADOPT:
            return self._adopt(command)
        test = StoryRoute.red_check(kind, start)
        if not dry and test is not None and self._stages.red_stale(story, start):
            start = test
        ran: typing.List[str] = []
        for step in StoryRoute.steps(kind, start, command.shared):
            stage = step.stage.value
            if not dry and Around.PAUSE in step.around:
                self._stages.pause(story)
            if step.move is Move.SKIP:
                self._lines.out(f"── stage {stage}  (skipped: {step.skipped.value if step.skipped else ''})")
                continue
            if Around.GATE_BEFORE in step.around:
                self._lines.out(f"── gate {stage}")
                if self._stages.gate(stage, story) != 0:
                    self._lines.err(f"factory: gate '{stage}' refused the story. Fix it before the stage runs.")
                    return 1
            if step.move is Move.BUILDER:
                built = self._builder(command, kind, step.stage)
                if built is not None:
                    return built
                ran.append(stage)
                continue
            if step.move is Move.CARRIED:
                ran.append(stage)
                continue
            # The reviews come before the judge: one process per perspective, at once.
            if Around.REVIEWS in step.around:
                code = self._stages.reviews(story, dry)
                if code != 0:
                    return code
            # The verifier runs where the judge would; resumed at the document stage alone it runs in its own context.
            if step.move is Move.VERIFIER:
                verified = self._verifier(command, kind)
                if verified != 0:
                    return verified
                ran += [name.value for name in StoryRoute.window(kind, Window.VERIFIER)]
                break
            artefact, holds = self._stages.artefact(story, stage), self._stages.holds(story, stage)
            # Resumed at a gated stage whose file exists: the gate decides first, on today's tree.
            if self._gate_first and step.stage == start and not dry and step.stage != DOCUMENT \
                    and Around.GATE_AFTER in step.around and holds:
                self._gate_first = False
                self._lines.out(f"── gate {stage}  (the file exists — checked before the stage is invoked)")
                if self._stages.quiet_gate(stage, story) == 0:
                    self._lines.out(f"factory: {artefact} already holds — stage '{stage}' is not invoked again.")
                    ran.append(stage)
                    continue
                if self._environment(story, stage):
                    return 1
            self._gate_first = False
            # A resumed story whose document file exists and was never refused: its gate decides first.
            if step.stage == DOCUMENT and not dry and holds and not self._stages.refused_before(story, stage) \
                    and not self._stages.delivered(story):
                self._lines.out("── gate document  (the file exists — checked before the stage is invoked)")
                if self._stages.quiet_gate(stage, story) == 0:
                    self._lines.out(f"factory: {artefact} already holds — the document stage is not invoked again.")
                    ran.append(stage)
                    break
            if dry:
                self._stages.dry(story, stage)
            else:
                code = self._stages.stage(story, stage)
                if code != 0:
                    return code
                after = self._after_stage(story, step.stage)
                if after is not None:
                    return after
            if Around.GATE_AFTER in step.around:
                self._lines.out(f"── gate {stage}")
                gate = 0 if dry else self._stages.gate(stage, story)
                if gate == 3:
                    return self._accepting(story)
                if gate != 0:
                    return self._refused(story, step.stage, f"gate '{stage}' refused")
            ran.append(stage)
            if Around.VERDICT in step.around and not dry:
                judged = self._judged(story, kind)
                if judged is not None:
                    return judged
                if self._runs(kind, ADOPT):
                    return self._adopt(command)
        # What ran, not what the script knows how to run.
        self._lines.out(f"factory: story {story} ran through {','.join(ran) or 'nothing'}.")
        if self._stages.in_worktree() and not dry and self._stages.resumes(story) == INTEGRATE:
            return self._integrate(command)
        return 0

    def _after_stage(self, story: str, stage: StageName) -> typing.Optional[Ended]:
        """After a stage's own process: the build stage found a defect in a test's own code — the round goes to the
        test stage, no person is asked —, or the stage ends with a needs-human section and has stopped."""
        if stage == BUILD and self._stages.sent_back(story):
            rounds = self._stages.bump(story)
            if StoryRoute.converged(rounds):
                self._lines.err(f"factory: the build stage sent the story back in round {rounds.value} — three rounds "
                                "did not converge. needs-human.")
                return 1
            self._lines.err(f"factory: the build stage found a defect in a test's own code — round {rounds.value} "
                            f"goes back to the {TEST.value} stage.")
            return TEST
        if self._stages.asks_human(story, stage.value):
            return self._stages.stopped_for_human(story, stage.value)
        return None

    def _builder(self, command: RunStoryCommand, kind: StoryKind, start: StageName) -> typing.Optional[Ended]:
        """Plan to tidy in one process, so each stage builds on what the one before read. The process runs each
        stage's gate itself; the run checks, not believes: the red proof must exist and the gates after it run again
        here. None when it holds."""
        story = command.story
        stages = [name.value for name in StoryRoute.window(kind, Window.BUILDER, start)]
        if not stages:
            return None
        code = self._stages.builder(story, stages, start.value, command.dry)
        if code != 0:
            return code
        if command.dry:
            return None
        # A `back: test` the session already acted on is no round: tidy.md newer than build.md says it repaired the
        # test, built again and tidied — the re-checked gates below decide.
        repaired = TIDY.value in stages and self._stages.repaired(story)
        sent_back = BUILD.value in stages and self._stages.sent_back(story)
        if sent_back and repaired:
            self._lines.out("factory: build.md names a defect in a test's own code that the shared session repaired "
                            "before tidy — the gates re-check it.")
        if sent_back and not repaired:
            rounds = self._stages.bump(story)
            if StoryRoute.converged(rounds):
                self._lines.err(f"factory: the build stage sent the story back in round {rounds.value} — three rounds "
                                "did not converge. needs-human.")
                return 1
            self._lines.err(f"factory: the build stage found a defect in a test's own code — round {rounds.value} "
                            "goes back to the test stage.")
            return TEST
        for stage in stages:
            if not self._stages.holds(story, stage):
                self._lines.err(f"factory: the shared stages produced no {self._stages.artefact(story, stage)} — "
                                f"stage '{stage}' is not finished.")
                return 1
            if self._stages.asks_human(story, stage):
                return self._stages.stopped_for_human(story, stage)
        # Checked, not believed: a story's tests were seen red; a journey's and an adoption's are green at their
        # test gate, so that gate runs again here.
        for stage in stages:
            traits = self._traits(stage)
            if not (Trait.IN_ORDER in traits and Trait.TESTED in traits and Trait.SUITE not in traits):
                continue
            if kind is not StoryKind.STORY:
                self._lines.out(f"── gate {stage}  (re-checked by the runner)")
                if self._stages.gate(stage, story) != 0:
                    self._lines.err(f"factory: the runner's re-check of gate '{stage}' refused the shared stages' work.")
                    return 1
            elif not self._stages.red_proof(story):
                self._lines.err(f"factory: the shared stages left no red proof ({self._stages.red_ledger(story)}) — "
                                f"the {stage} gate never saw the tests fail.")
                return 1
        for stage in stages:
            traits = self._traits(stage)
            if Trait.POST_GATED not in traits or (Trait.TESTED in traits and Trait.SUITE not in traits):
                continue
            self._lines.out(f"── gate {stage}  (re-checked by the runner)")
            if self._stages.gate(stage, story) != 0:
                if self._environment(story, stage):
                    return 1
                rounds = self._stages.bump(story)
                if StoryRoute.converged(rounds):
                    self._lines.err(f"factory: the runner's re-check of gate '{stage}' refused in round {rounds.value} "
                                    "— three rounds did not converge. needs-human.")
                    return 1
                self._lines.err(f"factory: the runner's re-check of gate '{stage}' refused — round {rounds.value} runs "
                                f"the shared stages again from '{stage}' with the gate's report.")
                return StageName(stage)
        return None

    def _verifier(self, command: RunStoryCommand, kind: StoryKind) -> Ended:
        """Judge and document in one process — never one process with the builder: the judge's independence from the
        builder is the point of the split."""
        story = command.story
        stages = [name.value for name in StoryRoute.window(kind, Window.VERIFIER)]
        code = self._stages.verifier(story, stages, command.dry)
        if code != 0 or command.dry:
            return code
        if not self._stages.holds(story, JUDGE.value):
            self._lines.err(f"factory: the shared stages produced no {self._stages.artefact(story, JUDGE.value)} — "
                            "stage 'judge' is not finished.")
            return 1
        if self._stages.asks_human(story, JUDGE.value):
            return self._stages.stopped_for_human(story, JUDGE.value)
        judged = self._judged(story, kind)
        if judged is not None:
            return judged
        if self._runs(kind, ADOPT):
            return self._adopt(command)
        if not self._stages.holds(story, DOCUMENT.value):
            self._lines.err(f"factory: the shared stages produced no {self._stages.artefact(story, DOCUMENT.value)} — "
                            "stage 'document' is not finished.")
            return 1
        if self._stages.asks_human(story, DOCUMENT.value):
            return self._stages.stopped_for_human(story, DOCUMENT.value)
        self._lines.out("── gate document  (re-checked by the runner)")
        gate = self._stages.gate(DOCUMENT.value, story)
        if gate == 3:
            return self._accepting(story)
        if gate != 0:
            return self._refused(story, DOCUMENT, "gate 'document' refused")
        return 0

    def _judged(self, story: str, kind: StoryKind) -> typing.Optional[Ended]:
        """The judge's verdict decides what comes next — read from its file, never assumed. None to go on."""
        verdict = self._stages.verdict(story)
        judged = StoryRoute.judged(verdict)
        judge = self._stages.artefact(story, JUDGE.value)
        if judged is Judged.PASS:
            self._lines.out("factory: judge verdict 'pass'.")
            return None
        if judged is Judged.AGAIN:
            rounds = self._stages.bump(story)
            if StoryRoute.converged(rounds):
                self._lines.err(f"factory: judge verdict 'changes-requested' in round {rounds.value} — three rounds "
                                "did not converge. needs-human.")
                return 1
            back = StoryRoute.back_for(kind, self._stages.back(story) or BUILD)
            self._lines.err(f"factory: judge verdict 'changes-requested' — round {rounds.value} goes back to the "
                            f"{back.value} stage.")
            return back
        if judged is Judged.CONFLICT:
            self._lines.err("factory: judge verdict 'story-conflict' — the story or the plan is wrong. This never goes "
                            f"back to the build stage. needs-human: read {judge}.")
            return 1
        if judged is Judged.MISSING:
            self._lines.err(f"factory: {judge} carries no 'verdict:' line — the judge stage is not finished.")
            return 1
        self._lines.err(f"factory: judge verdict '{verdict.value}' is not one of pass|changes-requested|story-conflict.")
        return 1

    def _adopt(self, command: RunStoryCommand) -> Ended:
        """Every scenario on a green test, the judge's pass, a break for every test the adoption wrote: passed, it
        delivers the story; refused, the test stage runs again, one round counted."""
        story = command.story
        self._lines.out("── gate adopt")
        if command.dry:
            return 0
        if self._stages.gate(ADOPT.value, story) == 0:
            if self._stages.in_worktree():
                return self._integrate(command)
            self._lines.out(f"factory: story {story} is delivered (adopted: checked, nothing built).")
            return 0
        if self._environment(story, ADOPT.value):
            return 1
        rounds = self._stages.bump(story)
        if StoryRoute.converged(rounds):
            self._lines.err(f"factory: gate 'adopt' refused in round {rounds.value} — three rounds did not converge. "
                            "needs-human.")
            return 1
        self._lines.err(f"factory: gate 'adopt' refused — round {rounds.value} runs the test stage again with the "
                        "gate's report.")
        return TEST

    def _integrate(self, command: RunStoryCommand) -> Ended:
        """Delivered is the integration; a refusal on the main line runs the build stage again."""
        integrated = self._stages.integrate(command.story, command.dry)
        return BUILD if integrated is None else integrated

    def _refused(self, story: str, stage: StageName, what: str) -> Ended:
        """A gate after its stage refused: no round where the machine is the cause, else a round from the refused
        stage — or the earlier one the story's state resumes at — while the rounds converge."""
        if self._environment(story, stage.value):
            return 1
        rounds = self._stages.bump(story)
        if StoryRoute.converged(rounds):
            self._lines.err(f"factory: {what} in round {rounds.value} — three rounds did not converge. needs-human.")
            return 1
        again = StoryRoute.again_from(stage, self._stages.resumes(story))
        self._lines.err(f"factory: {what} — round {rounds.value} runs stage '{again.value}' again with the gate's "
                        "report.")
        return again

    def _environment(self, story: str, stage: str) -> bool:
        """A refusal whose cause is the machine: no stage can put a tool on the PATH, so no round is counted."""
        reason = StoryRoute.environment(self._stages.report(story, stage))
        if reason is None:
            return False
        self._lines.err(f"factory: gate '{stage}' refused on the environment, not on the story — {reason.value}")
        self._lines.err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
        return True

    def _accepting(self, story: str) -> int:
        self._lines.err(f"factory: story {story} waits for a human's acceptance — answer it with /factory-decisions;")
        self._lines.err("factory:   the story holds the checkout until then.")
        return 3

    @staticmethod
    def _runs(kind: StoryKind, stage: StageName) -> bool:
        found = row(stage)
        return found is not None and kind in found.kinds

    @staticmethod
    def _traits(stage: str) -> typing.FrozenSet[Trait]:
        found = row(StageName(stage))
        return found.traits if found is not None else frozenset()

