"""Run a story: its stages from where it starts, a gate between them, a round back where a gate, the build stage or the
judge sends it, and its integration once it is delivered — the route decided by the workflow, every step taken
through the port."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.jump import Jumped, Next, RestartReason, Restarted, RuleId, Target
from ...domain.model.stage import Role, StageName, StoryKind, Trait, Window
from ...domain.model.refusal_history import Repetition
from ...domain.model.route import Around, Move
from ...domain.model.story_state import Judged, Rounds
from ..shared.run_lines import RunLines
from ..shared.run_outcome import GateOutcome, RunOutcome
from ..shared.stage_steps import StageSteps
from ..shared.story_run_journal import StoryRunJournal
from .check_stage import refusing
from .pipeline_rules import decides, jump
from .pipeline_workflow import role_of, workflow


#: What one pass of the route ends with: the run's exit, or the stage a round runs the story again from.
Ended = typing.Union[RunOutcome, StageName]


@dataclasses.dataclass
class Resume:
    """What one call of the run carries from pass to pass: whether a resumed stage whose file exists is gated
    before it runs — until the first stage it reaches takes the wish."""

    gate_first: bool


@dataclasses.dataclass(frozen=True)
class RunStoryCommand:
    story: str
    start: typing.Optional[str] = None
    dry: bool = False
    gate_first: bool = False                            #: a resumed stage whose file exists is gated before it runs
    shared: typing.FrozenSet[Window] = frozenset()      #: the windows that carry their stages in one process


class RunStoryInputPort(UseCase[RunStoryCommand, RunOutcome], typing.Protocol):
    """Run a story: how it ends."""


class RunStoryUseCase(RunStoryInputPort):
    """The story's stages, round after round — the executive of the story's process: it decides each next step with
    the workflow, takes it through the port, and reads where the story stands from the journal the port keeps. It
    ends when the story ran through, waits for a person, failed or did not converge, reached a limit, lost the
    checkout, or a person's file changed under a stage."""

    def __init__(self, journal: StoryRunJournal, steps: StageSteps, lines: RunLines) -> None:
        self._journal = journal
        self._steps = steps
        self._lines = lines

    def execute(self, command: RunStoryCommand) -> RunOutcome:
        start = StageName(command.start or role_of(Role.PLANS).value)
        resume = Resume(command.gate_first)              # this call's own, never the use case's
        while True:
            ended = self._route(command, start, resume)
            if isinstance(ended, StageName):
                start = ended
                continue
            return ended

    @decides(
        "RUN-ROUTE-1",
        "RUN-ROUTE-2",
        "RUN-ROUTE-3",
        "RUN-ROUTE-4",
        "RUN-ROUTE-5",
        "RUN-ROUTE-6",
        "RUN-ROUTE-7",
    )
    def _route(self, command: RunStoryCommand, start: StageName, resume: Resume) -> Ended:
        """One pass from <start> on."""
        story, dry = command.story, command.dry
        waiting = self._journal.open_decisions(story)
        if waiting:
            self._lines.err(f"factory: story {story} waits for a decision — no stage runs until it is answered:")
            for record in waiting:
                self._lines.err(f"factory:   {record}")
            self._lines.err("factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that "
                            "asked (--from <stage>).")
            return RunOutcome.WAITS_FOR_PERSON
        kind = self._journal.kind(story)
        # Every gate passed in the story's worktree: only the integration is left, and it delivers the story; an
        # adopted story whose judge passed: only the adopt gate.
        if start == role_of(Role.INTEGRATES):
            return self._integrate(command)
        if start == role_of(Role.ADOPTS):
            return self._adopt(command)
        stale = workflow().red_check(kind, start, jump("RUN-ROUTE-5"))
        if not dry and stale is not None and stale.stage is not None and self._journal.red_stale(story, start):
            start = stale.stage
            self._journal.restarted(story, Restarted(start, stale.rule, RestartReason.TEST_CHANGED))
        ran: typing.List[str] = []
        for step in workflow().steps(kind, start, command.shared):
            stage = step.stage.value
            if not dry and Around.PAUSE in step.around:
                self._steps.pause(story)
            if step.move is Move.SKIP:
                self._lines.out(f"── stage {stage}  (skipped: {step.skipped.value if step.skipped else ''})")
                continue
            if Around.GATE_BEFORE in step.around:
                self._lines.out(f"── gate {stage}")
                if self._steps.gate(stage, story) is not GateOutcome.PASSED:
                    self._lines.err(f"factory: gate '{stage}' refused the story. Fix it before the stage runs.")
                    return RunOutcome.FAILED
            if step.move is Move.BUILDER:
                built = self._builder(command, kind, step.stage, resume)
                if built is not None:
                    return built
                ran.append(stage)
                continue
            if step.move is Move.CARRIED:
                ran.append(stage)
                continue
            # The reviews come before the judge: one process per perspective, at once.
            if Around.REVIEWS in step.around:
                reviewed = self._steps.reviews(story, dry)
                if reviewed is not RunOutcome.RAN_THROUGH:
                    return reviewed
            # The verifier runs where the judge would; resumed at the document stage alone it runs in its own context.
            if step.move is Move.VERIFIER:
                verified = self._verifier(command, kind)
                if verified is not RunOutcome.RAN_THROUGH:
                    return verified
                ran += [name.value for name in workflow().window(kind, Window.VERIFIER)]
                break
            artefact, holds = self._journal.artefact(story, stage), self._journal.holds(story, stage)
            # Resumed at a gated stage whose file exists: the gate decides first, on today's tree.
            if resume.gate_first and step.stage == start and not dry and step.stage != role_of(Role.DELIVERS) \
                    and Around.GATE_AFTER in step.around and holds:
                resume.gate_first = False
                self._lines.out(f"── gate {stage}  (the file exists — checked before the stage is invoked)")
                if self._steps.quiet_gate(stage, story) is GateOutcome.PASSED:
                    self._lines.out(f"factory: {artefact} already holds — stage '{stage}' is not invoked again.")
                    ran.append(stage)
                    continue
                if self._environment(story, stage):
                    return RunOutcome.FAILED
            resume.gate_first = False
            # A resumed story whose document file exists and was never refused: its gate decides first.
            if step.stage == role_of(Role.DELIVERS) and not dry and holds and not self._journal.refused_before(story, stage) \
                    and not self._journal.delivered(story):
                self._lines.out("── gate document  (the file exists — checked before the stage is invoked)")
                if self._steps.quiet_gate(stage, story) is GateOutcome.PASSED:
                    self._lines.out(f"factory: {artefact} already holds — the document stage is not invoked again.")
                    ran.append(stage)
                    break
            if dry:
                self._steps.dry(story, stage)
            else:
                ran_stage = self._steps.stage(story, stage)
                if ran_stage is not RunOutcome.RAN_THROUGH:
                    return ran_stage
                after = self._after_stage(story, kind, step.stage)
                if after is not None:
                    return after
            if Around.GATE_AFTER in step.around:
                self._lines.out(f"── gate {stage}")
                gate = GateOutcome.PASSED if dry else self._steps.gate(stage, story)
                if gate is GateOutcome.WAITS_FOR_PERSON:
                    return self._accepting(story)
                if gate is not GateOutcome.PASSED:
                    return self._refused(story, kind, step.stage, f"gate '{stage}' refused")
            ran.append(stage)
            if step.stage == role_of(Role.PLANS) and not dry:
                adopted = self._adopted(command, kind, resume)
                if adopted is not None:
                    return adopted
            if Around.VERDICT in step.around and not dry:
                judged = self._judged(story, kind)
                if judged is not None:
                    return judged
                if self._runs(kind, role_of(Role.ADOPTS)):
                    return self._adopt(command)
        # What ran, not what the script knows how to run.
        self._lines.out(f"factory: story {story} ran through {','.join(ran) or 'nothing'}.")
        if self._journal.in_worktree() and not dry and self._journal.resumes(story) == role_of(Role.INTEGRATES):
            return self._integrate(command)
        return RunOutcome.RAN_THROUGH

    def _adopted(self, command: RunStoryCommand, kind: StoryKind, resume: Resume) -> typing.Optional[Ended]:
        """The plan gate adopted the whole story (WP-165): its kind is read once per pass, so the pass ends here and
        the story goes on as an adoption, from its plan. A split leaves the story's kind as it was: it builds the rest."""
        now = self._journal.kind(command.story)
        if now is kind:
            return None
        self._lines.out(f"factory: the plan found every scenario of {command.story} holding today — it goes on as an "
                        f"adoption.")
        self._journal.restarted(command.story, Restarted(role_of(Role.PLANS), RuleId("RUN-ROUTE-7"),
                                                         RestartReason.ADOPTED))
        return self._route(command, role_of(Role.PLANS), resume)

    @decides("RUN-BACK-1")
    def _after_stage(self, story: str, kind: StoryKind, stage: StageName) -> typing.Optional[Ended]:
        """After a stage's own process: the build stage found a defect in a test's own code — the round goes to the
        test stage, no person is asked —, or the stage ends with a needs-human section and has stopped."""
        if stage == role_of(Role.BUILDS) and self._journal.sent_back(story):
            return self._sent_back(story, kind)
        if self._journal.asks_human(story, stage.value):
            return self._steps.stopped_for_human(story, stage.value)
        return None

    @decides("RUN-WINDOW-1")
    def _builder(self, command: RunStoryCommand, kind: StoryKind, start: StageName,
                 resume: Resume) -> typing.Optional[Ended]:
        """Plan to tidy in one process, so each stage builds on what the one before read. The process runs each
        stage's gate itself; the run checks, not believes: the red proof must exist and the gates after it run again
        here. None when it holds."""
        story = command.story
        stages = [name.value for name in workflow().window(kind, Window.BUILDER, start)]
        if not stages:
            return None
        built = self._steps.builder(story, stages, start.value, command.dry)
        if built is not RunOutcome.RAN_THROUGH:
            return built
        if command.dry:
            return None
        if role_of(Role.PLANS).value in stages:
            adopted = self._adopted(command, kind, resume)
            if adopted is not None:
                return adopted
        # A `back: test` the session already acted on is no round: tidy.md newer than build.md says it repaired the
        # test, built again and tidied — the re-checked gates below decide.
        repaired = role_of(Role.TIDIES).value in stages and self._journal.repaired(story)
        sent_back = role_of(Role.BUILDS).value in stages and self._journal.sent_back(story)
        if sent_back and repaired:
            self._lines.out("factory: build.md names a defect in a test's own code that the shared session repaired "
                            "before tidy — the gates re-check it.")
        if sent_back and not repaired:
            return self._sent_back(story, kind)
        for stage in stages:
            if not self._journal.holds(story, stage):
                self._lines.err(f"factory: the shared stages produced no {self._journal.artefact(story, stage)} — "
                                f"stage '{stage}' is not finished.")
                return RunOutcome.FAILED
            if self._journal.asks_human(story, stage):
                return self._steps.stopped_for_human(story, stage)
        # Checked, not believed: a story's tests were seen red; a journey's and an adoption's are green at their
        # test gate, so that gate runs again here.
        for stage in stages:
            traits = self._traits(stage)
            if not (Trait.IN_ORDER in traits and Trait.TESTED in traits and Trait.SUITE not in traits):
                continue
            if kind is not StoryKind.STORY:
                self._lines.out(f"── gate {stage}  (re-checked by the runner)")
                if self._steps.gate(stage, story) is not GateOutcome.PASSED:
                    self._lines.err(f"factory: the runner's re-check of gate '{stage}' refused the shared stages' work.")
                    return RunOutcome.FAILED
            elif not self._journal.red_proof(story):
                self._lines.err(f"factory: the shared stages left no red proof ({self._journal.red_ledger(story)}) — "
                                f"the {stage} gate never saw the tests fail.")
                return RunOutcome.FAILED
        for stage in stages:
            traits = self._traits(stage)
            if Trait.POST_GATED not in traits or (Trait.TESTED in traits and Trait.SUITE not in traits):
                continue
            self._lines.out(f"── gate {stage}  (re-checked by the runner)")
            if self._steps.gate(stage, story) is not GateOutcome.PASSED:
                return self._refused(story, kind, StageName(stage), f"the runner's re-check of gate '{stage}' refused")
        return None

    def _sent_back(self, story: str, kind: StoryKind) -> Ended:
        """The build stage found a defect in a test's own code: a round, where RUN-BACK-1 sends it."""
        rounds = self._round(story, "the build stage sent the story back")
        if rounds is None:
            return RunOutcome.FAILED
        went = workflow().jump(kind, role_of(Role.BUILDS), jump("RUN-BACK-1"))
        return self._went(story, role_of(Role.BUILDS), went, f"factory: the build stage found a defect in a test's own code ({went.rule.value}) — "
                                f"round {rounds.value} goes back to the {{stage}} stage.")

    @decides("RUN-WINDOW-2")
    def _verifier(self, command: RunStoryCommand, kind: StoryKind) -> Ended:
        """Judge and document in one process — never one process with the builder: the judge's independence from the
        builder is the point of the split."""
        story = command.story
        stages = [name.value for name in workflow().window(kind, Window.VERIFIER)]
        verified = self._steps.verifier(story, stages, command.dry)
        if verified is not RunOutcome.RAN_THROUGH or command.dry:
            return verified
        if not self._journal.holds(story, role_of(Role.JUDGES).value):
            self._lines.err(f"factory: the shared stages produced no {self._journal.artefact(story, role_of(Role.JUDGES).value)} — "
                            "stage 'judge' is not finished.")
            return RunOutcome.FAILED
        if self._journal.asks_human(story, role_of(Role.JUDGES).value):
            return self._steps.stopped_for_human(story, role_of(Role.JUDGES).value)
        judged = self._judged(story, kind)
        if judged is not None:
            return judged
        if self._runs(kind, role_of(Role.ADOPTS)):
            return self._adopt(command)
        if not self._journal.holds(story, role_of(Role.DELIVERS).value):
            self._lines.err(f"factory: the shared stages produced no {self._journal.artefact(story, role_of(Role.DELIVERS).value)} — "
                            "stage 'document' is not finished.")
            return RunOutcome.FAILED
        if self._journal.asks_human(story, role_of(Role.DELIVERS).value):
            return self._steps.stopped_for_human(story, role_of(Role.DELIVERS).value)
        self._lines.out("── gate document  (re-checked by the runner)")
        gate = self._steps.gate(role_of(Role.DELIVERS).value, story)
        if gate is GateOutcome.WAITS_FOR_PERSON:
            return self._accepting(story)
        if gate is not GateOutcome.PASSED:
            return self._refused(story, kind, role_of(Role.DELIVERS), "gate 'document' refused")
        return RunOutcome.RAN_THROUGH

    @decides("RUN-VERDICT-1")
    def _judged(self, story: str, kind: StoryKind) -> typing.Optional[Ended]:
        """The judge's verdict decides what comes next — read from its file, never assumed. None to go on."""
        judged = self._journal.verdict(story)
        judge = self._journal.artefact(story, role_of(Role.JUDGES).value)
        if judged is Judged.PASS:
            self._lines.out("factory: judge verdict 'pass'.")
            # how strong the story's tests are, read after the judge — a measure, never a gate (WP-190 A)
            self._steps.measure_mutation(story)
            return None
        if judged is Judged.AGAIN:
            rounds = self._round(story, "judge verdict 'changes-requested'")
            if rounds is None:
                return RunOutcome.FAILED
            named = Target((self._journal.back(story) or role_of(Role.BUILDS)).value)
            back = workflow().chosen(kind, role_of(Role.JUDGES), jump("RUN-VERDICT-1"), named)
            return self._went(story, role_of(Role.JUDGES), back, f"factory: judge verdict 'changes-requested' ({back.rule.value}) — round "
                                    f"{rounds.value} goes back to the {{stage}} stage.")
        if judged is Judged.CONFLICT:
            self._lines.err("factory: judge verdict 'story-conflict' — the story or the plan is wrong. This never goes "
                            f"back to the build stage. needs-human: read {judge}.")
            return RunOutcome.FAILED
        if judged is Judged.MISSING:
            self._lines.err(f"factory: {judge} carries no 'verdict:' line — the judge stage is not finished.")
            return RunOutcome.FAILED
        self._lines.err(f"factory: {judge} carries a verdict that is not one of pass|changes-requested|story-conflict.")
        return RunOutcome.FAILED

    @decides("RUN-ADOPT-1")
    def _adopt(self, command: RunStoryCommand) -> Ended:
        """Every scenario on a green test, the judge's pass, a break for every test the adoption wrote: passed, it
        delivers the story; refused, the test stage runs again, one round counted."""
        story = command.story
        self._lines.out("── gate adopt")
        if command.dry:
            return RunOutcome.RAN_THROUGH
        if self._steps.gate(role_of(Role.ADOPTS).value, story) is GateOutcome.PASSED:
            if self._journal.in_worktree():
                return self._integrate(command)
            self._lines.out(f"factory: story {story} is delivered (adopted: checked, nothing built).")
            return RunOutcome.RAN_THROUGH
        if self._environment(story, role_of(Role.ADOPTS).value):
            return RunOutcome.FAILED
        rounds = self._round(story, "gate 'adopt' refused")
        if rounds is None:
            return RunOutcome.FAILED
        went = workflow().jump(self._journal.kind(story), role_of(Role.ADOPTS), jump("RUN-ADOPT-1"))
        return self._went(story, role_of(Role.ADOPTS), went, f"factory: gate 'adopt' refused ({went.rule.value}) — round {rounds.value} runs the "
                                f"{{stage}} stage again with the gate's report.")

    def _integrate(self, command: RunStoryCommand) -> Ended:
        """Delivered is the integration; a refusal on the main line runs the build stage again."""
        integrated = self._steps.integrate(command.story, command.dry)
        if integrated is not None:
            return integrated
        # a refusal on the main line, not a merge that moved: the way of RUN-INTEGRATE-1 that builds again
        went = workflow().chosen(self._journal.kind(command.story), role_of(Role.INTEGRATES), jump("RUN-INTEGRATE-1"),
                                 Target(role_of(Role.BUILDS).value))
        return self._went(command.story, role_of(Role.INTEGRATES), went, "")

    @decides(
        "RUN-ROUNDS-1",
        "RUN-ROUNDS-2",
        "RUN-ROUNDS-3",
        "RUN-ROUNDS-4",
    )
    def _refused(self, story: str, kind: StoryKind, stage: StageName, what: str) -> Ended:
        """A gate refused: no round where the machine is the cause; else the rules that failed say where the story
        goes (`workflow().after_refusal`) — a rule that stops ends the run, else a round from the stage they name, the
        refused one or the earlier one the story's state resumes at, while the rounds converge. A refusal that repeats
        the one before starts its round fresh (RUN-ROUNDS-3); repeated again after that, the run stops for a person
        (RUN-ROUNDS-4)."""
        if self._environment(story, stage.value):
            return RunOutcome.FAILED
        self._journal.record_round(story, stage)
        failed = self._journal.report(story, stage.value).refused_checks()
        went = workflow().after_refusal(kind, stage, self._journal.resumes(story),
                                        refusing(stage.value, [name.value for name in failed]), RuleId("RUN-ROUNDS-1"))
        if went.stage is None:
            self._lines.err(f"factory: {what} ({went.rule.value}) — the rule stops the run. needs-human.")
            return RunOutcome.FAILED
        repetition = self._journal.refusal_history(story).repetition()
        if repetition is Repetition.REPEATED_AFTER_FRESH:
            self._journal.stopped_by_repetition(story, stage)
            self._lines.err(f"factory: {what} (RUN-ROUNDS-4) — the fresh restart was refused as the attempt before it; "
                            f"the round record names each round. needs-human.")
            return RunOutcome.FAILED
        rounds = self._round(story, what)
        if rounds is None:
            return RunOutcome.FAILED
        if repetition is Repetition.REPEATED and went.stage is not None:
            self._journal.restart_fresh(story, went.stage)
            return self._went(story, stage, went, f"factory: {what} as the round before (RUN-ROUNDS-3) — round "
                                                  f"{rounds.value} runs stage '{{stage}}' afresh: the story, the plan, "
                                                  f"the gate's report and the round record, not the earlier attempt.")
        return self._went(story, stage, went, f"factory: {what} ({went.rule.value}) — round {rounds.value} runs stage '{{stage}}' "
                                "again with the gate's report.")

    def _round(self, story: str, what: str) -> typing.Optional[Rounds]:
        """One more round counted — None where the rounds did not converge (`Rounds.converged`): <what> said, the run
        ends for a person."""
        rounds = self._journal.bump(story)
        if rounds.converged():
            self._lines.err(f"factory: {what} in round {rounds.value} — three rounds did not converge. needs-human.")
            return None
        return rounds

    def _went(self, story: str, here: StageName, went: Next, said: str) -> Ended:
        """The stage a rule sent the story to from <here>, <said> with it and kept in the journal; a rule that sends it
        nowhere stops the run."""
        if went.stage is None:
            self._lines.err(f"factory: {went.rule.value} sends the story nowhere from here — the run stops. needs-human.")
            return RunOutcome.FAILED
        self._journal.jumped(story, Jumped(here, went.stage, went.rule))
        if said:
            self._lines.err(said.format(stage=went.stage.value))
        return went.stage

    def _environment(self, story: str, stage: str) -> bool:
        """A refusal whose cause is the machine: no stage can put a tool on the PATH, so no round is counted."""
        reason = self._journal.report(story, stage).environment()
        if reason is None:
            return False
        self._lines.err(f"factory: gate '{stage}' refused on the environment, not on the story — {reason.value}")
        self._lines.err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
        return True

    @decides("RUN-ACCEPT-1")
    def _accepting(self, story: str) -> RunOutcome:
        self._lines.err(f"factory: story {story} waits for a human's acceptance — answer it with /factory-decisions;")
        self._lines.err("factory:   the story holds the checkout until then.")
        return RunOutcome.WAITS_FOR_PERSON

    @staticmethod
    def _runs(kind: StoryKind, stage: StageName) -> bool:
        found = workflow().stage(stage)
        return found is not None and kind in found.kinds

    @staticmethod
    def _traits(stage: str) -> typing.FrozenSet[Trait]:
        found = workflow().stage(StageName(stage))
        return found.traits if found is not None else frozenset()

