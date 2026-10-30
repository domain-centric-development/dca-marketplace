"""A story's route and its run over stand-ins for the runner: which stage runs how, where a round goes back to, and
that a round is one more pass, never a run inside a run."""

import unittest

import support  # noqa: F401 — puts the package on the path
# the rules a refused gate routes by, registered as the runner's composition root registers them
from dca_factory.delivery.application.delivery import pass_actions, process_checks, stage_checks  # noqa: F401
from dca_factory.delivery.application.delivery.pipeline_rules import jump
from dca_factory.delivery.application.delivery.run_story import RunStoryCommand, RunStoryUseCase
from dca_factory.delivery.domain.model.jump import Jump, Next, RuleId, Target
from dca_factory.delivery.domain.model.workflow_rule import Outcome, OutcomeState, RuleText
from dca_factory.delivery.domain.model.stage import StageName, StoryKind, Window
from dca_factory.delivery.domain.model.story_state import GateReport, HandOverText, Rounds, VerdictWord
from dca_factory.delivery.application.delivery.integrate_story import IntegrateStoryCommand, IntegrateStoryUseCase
from dca_factory.delivery.domain.service.story_route import Around, Judged, Move, Refusal, StoryRoute


def names(*words):
    return tuple(StageName(word) for word in words)


class Route(unittest.TestCase):

    def test_a_story_runs_every_stage_in_its_own_process_with_the_gates_around_them(self):
        steps = StoryRoute.steps(StoryKind.STORY, StageName("plan"), frozenset())
        self.assertEqual([(s.stage.value, s.move) for s in steps],
                         [(n, Move.STAGE) for n in ("plan", "test", "build", "tidy", "judge", "document")])
        self.assertIn(Around.GATE_BEFORE, steps[0].around)
        self.assertIn(Around.GATE_AFTER, steps[1].around)
        self.assertEqual({Around.PAUSE, Around.REVIEWS, Around.VERDICT}, set(steps[4].around))

    def test_a_shared_builder_carries_its_window_and_requests_wait_until_it_is_done(self):
        steps = StoryRoute.steps(StoryKind.STORY, StageName("test"), frozenset((Window.BUILDER, Window.VERIFIER)))
        self.assertEqual([(s.stage.value, s.move) for s in steps],
                         [("test", Move.BUILDER), ("build", Move.CARRIED), ("tidy", Move.CARRIED),
                          ("judge", Move.VERIFIER)])
        self.assertEqual([Around.PAUSE in s.around for s in steps], [True, False, False, True])

    def test_an_answer_applies_where_it_names_and_resumes_at_the_earlier_stage(self):
        plan, test, build = names("plan", "test", "build")
        self.assertEqual(StoryRoute.applying(build, test), test)
        self.assertEqual(StoryRoute.applying(build, StageName("nowhere")), build)
        self.assertEqual(StoryRoute.resumes_at(plan, test), plan)
        self.assertEqual(StoryRoute.resumes_at(build, test), test)
        self.assertEqual(StoryRoute.resumes_at(StageName("integrate"), test), test)

    def test_an_adoption_changes_nothing_so_its_judge_gets_no_reviews(self):
        for shared in (frozenset(), frozenset((Window.VERIFIER,))):
            judge = [s for s in StoryRoute.steps(StoryKind.ADOPT, StageName("plan"), shared) if s.stage.value == "judge"]
            self.assertEqual(len(judge), 1)
            self.assertNotIn(Around.REVIEWS, judge[0].around)
        for kind in (StoryKind.STORY, StoryKind.JOURNEY, StoryKind.TASK):
            judge = [s for s in StoryRoute.steps(kind, StageName("plan"), frozenset()) if s.stage.value == "judge"]
            self.assertIn(Around.REVIEWS, judge[0].around)

    def test_a_kind_skips_what_it_does_not_run_and_says_why(self):
        steps = StoryRoute.steps(StoryKind.TASK, StageName("plan"), frozenset())
        skipped = [s for s in steps if s.move is Move.SKIP]
        self.assertEqual([s.stage.value for s in skipped], ["test"])
        self.assertIn("a task has no criterion to test", skipped[0].skipped.value)

    def test_the_windows_carry_what_the_kind_runs_from_where_it_starts(self):
        self.assertEqual(StoryRoute.window(StoryKind.TASK, Window.BUILDER), names("plan", "build", "tidy"))
        self.assertEqual(StoryRoute.window(StoryKind.STORY, Window.BUILDER, StageName("build")), names("build", "tidy"))
        self.assertEqual(StoryRoute.window(StoryKind.ADOPT, Window.VERIFIER), names("judge"))

    def test_the_judges_back_test_sends_the_story_to_the_test_stage_anything_else_to_the_build(self):
        back = lambda kind, text: StoryRoute.judged_back(kind, HandOverText(text)).value
        self.assertEqual("test", back(StoryKind.STORY, "verdict: changes-requested\nback: `test`\n"))
        self.assertEqual("build", back(StoryKind.STORY, "verdict: changes-requested\n"))
        self.assertEqual("build", back(StoryKind.STORY, "verdict: changes-requested\nBack: build\n"))
        self.assertEqual("test", back(StoryKind.JOURNEY, "verdict: changes-requested\n"))
        self.assertEqual("test", back(StoryKind.ADOPT, "verdict: changes-requested\n"))

    def test_a_round_goes_back_to_the_last_builder_stage_the_kind_runs(self):
        self.assertEqual(StoryRoute.back_for(StoryKind.STORY, StageName("build")), StageName("build"))
        self.assertEqual(StoryRoute.back_for(StoryKind.JOURNEY, StageName("build")), StageName("test"))
        self.assertEqual(StoryRoute.again_from(StageName("tidy"), StageName("build")), StageName("build"))
        self.assertEqual(StoryRoute.again_from(StageName("tidy"), StageName("judge")), StageName("tidy"))

    def test_the_verdict_the_rounds_and_the_environment(self):
        self.assertIs(StoryRoute.judged(VerdictWord("changes-requested")), Judged.AGAIN)
        self.assertIs(StoryRoute.judged(VerdictWord("")), Judged.MISSING)
        self.assertIs(StoryRoute.judged(VerdictWord("maybe")), Judged.UNKNOWN)
        self.assertIsNone(StoryRoute.converged(Rounds(2)))
        self.assertIsNotNone(StoryRoute.converged(Rounds(3)))
        report = GateReport("gate:fail environment — no java on the PATH\ngate:fail story S stage build")
        self.assertEqual(StoryRoute.environment(report).value, "no java on the PATH")
        self.assertIsNone(StoryRoute.environment(GateReport("gate:fail tests-red")))

    def test_a_stale_red_proof_sends_a_story_where_its_rule_says_from_a_listing_stage_only(self):
        stale = jump("RUN-ROUTE-5")
        self.assertEqual(StoryRoute.red_check(StoryKind.STORY, StageName("build"), stale),
                         Next(StageName("test"), RuleId("RUN-ROUTE-5")))
        self.assertIsNone(StoryRoute.red_check(StoryKind.STORY, StageName("test"), stale))
        self.assertIsNone(StoryRoute.red_check(StoryKind.STORY, StageName("judge"), stale))
        self.assertIsNone(StoryRoute.red_check(StoryKind.TASK, StageName("build"), stale))


def way(rule_id, *targets):
    return Jump(RuleId(rule_id), tuple(Target(t) for t in targets))


class Jumps(unittest.TestCase):
    """Where the elements of the workflow send a story: the rules decide, the run follows."""

    ROUNDS = RuleId("RUN-ROUNDS-1")

    def refused(self, *jumps, stage="build", resumes=None, kind=StoryKind.STORY):
        return StoryRoute.after_refusal(kind, StageName(stage), resumes and StageName(resumes), jumps, self.ROUNDS)

    def test_a_refusal_whose_rules_name_no_way_runs_the_refused_stage_again(self):
        self.assertEqual(self.refused(way("GATE-TESTS-GREEN")), Next(StageName("build"), RuleId("GATE-TESTS-GREEN")))
        self.assertEqual(self.refused(), Next(StageName("build"), self.ROUNDS))

    def test_a_rule_that_names_a_stage_sends_the_story_there(self):
        self.assertEqual(self.refused(way("GATE-TESTS-GREEN"), way("GATE-RED-PROOF", "test")),
                         Next(StageName("test"), RuleId("GATE-RED-PROOF")))

    def test_the_earliest_way_wins_and_the_story_state_counts_as_one(self):
        self.assertEqual(self.refused(way("GATE-RED-PROOF", "test"), stage="document", resumes="plan"),
                         Next(StageName("plan"), self.ROUNDS))
        self.assertEqual(self.refused(way("GATE-ACCEPTANCE", "plan"), way("GATE-RED-PROOF", "test"), stage="document"),
                         Next(StageName("plan"), RuleId("GATE-ACCEPTANCE")))

    def test_a_rule_that_stops_beats_every_way(self):
        self.assertEqual(self.refused(way("GATE-ACCEPTANCE", "plan"), way("GATE-OWNED", "stop"), stage="document"),
                         Next(None, RuleId("GATE-OWNED")))

    def test_a_way_the_kind_does_not_run_goes_to_its_builder_stage_before(self):
        self.assertEqual(self.refused(way("GATE-X", "test"), stage="tidy", kind=StoryKind.TASK),
                         Next(StageName("plan"), RuleId("GATE-X")))

    def test_a_choice_outside_the_rule_stops_the_run(self):
        verdict = jump("RUN-VERDICT-1")
        self.assertEqual(StoryRoute.chosen(StoryKind.STORY, StageName("judge"), verdict, Target("test")),
                         Next(StageName("test"), RuleId("RUN-VERDICT-1")))
        self.assertEqual(StoryRoute.chosen(StoryKind.STORY, StageName("judge"), verdict, Target("plan")),
                         Next(None, RuleId("RUN-VERDICT-1")))

    def test_the_checks_a_report_failed_once_each_without_its_closing_line(self):
        report = GateReport("gate:pass story — ok\ngate:fail red-proof — x\ngate:fail red-proof — y\n"
                            "gate:fail tests-green — z\ngate:fail story S-1 stage build")
        self.assertEqual([n.value for n in StoryRoute.refused_checks(report)], ["red-proof", "tests-green"])

    def test_a_rule_goes_nowhere_but_a_stage_again_or_stop(self):
        with self.assertRaises(ValueError):
            Outcome(OutcomeState.FAIL, RuleText("f"), (Target("nowhere"),))

    def test_a_runner_rule_nobody_registered_is_an_error(self):
        with self.assertRaises(KeyError):
            jump("RUN-NOBODY-1")


class IntegrationRefusals(unittest.TestCase):

    def test_what_the_failed_checks_on_the_main_line_say(self):
        close = "gate:fail story S-1 stage integrate"
        self.assertEqual(StoryRoute.integration(GateReport(f"gate:fail moved — main moved\n{close}")),
                         frozenset((Refusal.MOVED,)))
        self.assertEqual(StoryRoute.integration(GateReport(f"gate:fail moved\ngate:fail main-tests — x\n{close}")),
                         frozenset((Refusal.MAIN_TESTS,)))
        self.assertEqual(StoryRoute.integration(GateReport(f"gate:fail checkout — dirty\n{close}")),
                         frozenset((Refusal.CHECKOUT,)))
        self.assertEqual(StoryRoute.integration(GateReport(f"gate:fail tests-green\n{close}")), frozenset())


class Lines:
    def __init__(self):
        self.said = []

    def out(self, line):
        self.said.append(line)

    def err(self, line):
        self.said.append(line)


class Stages:
    """A story whose stages all write their files; the gates refuse as told, the judge says what it is told."""

    def __init__(self, refusals=(), verdicts=("pass",), kind=StoryKind.STORY, reports=None):
        self.refusals = list(refusals)          # the stages whose gate refuses, once each, in order
        self.reports = reports or {}            # what a refusal's report says, per stage
        self.verdicts = list(verdicts)
        self._kind = kind
        self.ran, self.rounds = [], 0

    def open_decisions(self, story):
        return []

    def kind(self, story):
        return self._kind

    def red_stale(self, story, start):
        return False

    def pause(self, story):
        pass

    def gate(self, stage, story):
        self.ran.append(f"gate {stage}")
        if self.refusals and self.refusals[0] == stage:
            self.refusals.pop(0)
            return 1
        return 0

    quiet_gate = gate

    def report(self, story, stage):
        return GateReport(self.reports.get(stage, "gate:fail tests-red"))

    def artefact(self, story, stage):
        return f"runs/{story}/{stage}.md"

    def holds(self, story, stage):
        return False

    def refused_before(self, story, stage):
        return False

    def delivered(self, story):
        return False

    def asks_human(self, story, stage):
        return False

    def stopped_for_human(self, story, stage):
        return 3

    def stage(self, story, stage):
        self.ran.append(stage)
        return 0

    def dry(self, story, stage):
        self.ran.append(f"dry {stage}")

    def reviews(self, story, dry):
        return 0

    def sent_back(self, story):
        return False

    def bump(self, story):
        self.rounds += 1
        return Rounds(self.rounds)

    def resumes(self, story):
        return None

    def verdict(self, story):
        return VerdictWord(self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0])

    def back(self, story):
        return None

    def in_worktree(self):
        return False


def run(stages, start=None):
    lines = Lines()
    code = RunStoryUseCase(stages, lines).execute(RunStoryCommand("S-1", start))
    return code, lines.said


class AdoptedAtPlan(Stages):
    """The plan gate turned the story into an adoption while the plan stage ran (WP-165)."""

    def stage(self, story, stage):
        if stage == "plan" and self._kind is StoryKind.STORY:
            self._kind = StoryKind.ADOPT
        return super().stage(story, stage)


class Run(unittest.TestCase):

    def test_a_story_the_plan_adopted_goes_on_as_an_adoption_from_its_plan(self):
        stages = AdoptedAtPlan()
        code, said = run(stages)
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[:3], ["gate plan", "plan", "gate plan"])
        self.assertNotIn("build", stages.ran)
        self.assertTrue(any("goes on as an adoption" in line for line in said))

    def test_a_story_runs_through_with_a_gate_after_each_gated_stage(self):
        stages = Stages()
        code, said = run(stages)
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran, ["gate plan", "plan", "test", "gate test", "build", "gate build", "tidy",
                                      "gate tidy", "judge", "document", "gate document"])
        self.assertIn("factory: story S-1 ran through plan,test,build,tidy,judge,document.", said)

    def test_a_refused_gate_runs_its_stage_again_as_one_more_pass(self):
        stages = Stages(refusals=("build",))
        code, said = run(stages, "build")
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[:4], ["build", "gate build", "build", "gate build"])
        self.assertIn("factory: gate 'build' refused (GATE-TESTS-RED) — round 1 runs stage 'build' again with the "
                      "gate's report.", said)

    def test_a_refused_gate_goes_where_its_failed_rule_says(self):
        stages = Stages(refusals=("build",), reports={"build": "gate:fail red-proof — a test changed"})
        code, said = run(stages, "build")
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[:4], ["build", "gate build", "test", "gate test"])
        self.assertIn("factory: gate 'build' refused (GATE-RED-PROOF) — round 1 runs stage 'test' again with the "
                      "gate's report.", said)

    def test_an_acceptance_that_asks_for_a_correction_plans_the_story_again(self):
        stages = Stages(refusals=("document",), reports={"document": "gate:fail acceptance — a correction"})
        code, _said = run(stages, "document")
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[:4], ["document", "gate document", "gate plan", "plan"])

    def test_a_rule_that_stops_ends_the_run_without_a_round(self):
        stages = Stages(refusals=("build",), reports={"build": "gate:fail owned — the story changed under a stage"})
        code, said = run(stages, "build")
        self.assertEqual((code, stages.rounds), (1, 0))
        self.assertIn("factory: gate 'build' refused (GATE-OWNED) — the rule stops the run. needs-human.", said)

    def test_three_refusals_do_not_converge(self):
        stages = Stages(refusals=("tidy", "tidy", "tidy"))
        code, said = run(stages, "tidy")
        self.assertEqual((code, stages.rounds), (1, 3))
        self.assertIn("factory: gate 'tidy' refused in round 3 — three rounds did not converge. needs-human.", said)

    def test_changes_requested_go_back_to_the_build_stage(self):
        stages = Stages(verdicts=("changes-requested", "pass"))
        code, said = run(stages, "judge")
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[:3], ["judge", "build", "gate build"])
        self.assertIn("factory: judge verdict 'changes-requested' (RUN-VERDICT-1) — round 1 goes back to the build "
                      "stage.", said)

    def test_a_story_conflict_stops_for_a_person(self):
        code, said = run(Stages(verdicts=("story-conflict",)), "judge")
        self.assertEqual(code, 1)
        self.assertTrue(any("story-conflict" in line and "needs-human" in line for line in said))

    def test_an_adopted_story_ends_with_its_gate_after_the_judge(self):
        stages = Stages(kind=StoryKind.ADOPT)
        code, said = run(stages)
        self.assertEqual(code, 0)
        self.assertEqual(stages.ran[-2:], ["judge", "gate adopt"])
        self.assertIn("factory: story S-1 is delivered (adopted: checked, nothing built).", said)


class Integration:
    """A main line that moves on <moves> times, then a gate that says what it is told."""

    def __init__(self, moves=0, refusal="", lost=()):
        self.moves, self.refusal, self._lost = moves, refusal, list(lost)
        self.did, self.rounds, self.held = [], 0, 0

    def lock(self):
        self.held += 1

    def unlock(self):
        self.held -= 1

    def step(self, story, work):
        return work()

    def prepare(self, story):
        self.did.append("prepare")
        return 0, ""

    def session(self, story, conflicts, lost):
        self.did.append("session")
        return None

    def lost(self, story):
        return [self._lost.pop(0)] if self._lost else []

    def lost_text(self, lost):
        return "lost"

    def gate(self, story):
        self.did.append("gate")
        if self.moves:
            self.moves -= 1
            self.last = "gate:fail moved"
            return 1
        self.last = self.refusal
        return 1 if self.refusal else 0

    def report(self, story):
        return GateReport(self.last)

    def report_place(self, story):
        return "runs/S-1/.gate-integrate.txt"

    def published(self):
        return False

    def worktree(self):
        return "wt"

    def relink(self, story):
        self.did.append("relink")

    def bump(self, story):
        self.rounds += 1
        return Rounds(self.rounds)


class Integrate(unittest.TestCase):

    def test_a_main_line_that_moved_on_is_merged_again(self):
        integration = Integration(moves=1)
        code = IntegrateStoryUseCase(integration, Lines()).execute(IntegrateStoryCommand("S-1"))
        self.assertEqual(code, 0)
        self.assertEqual(integration.did, ["prepare", "gate", "prepare", "gate"])
        self.assertEqual(integration.held, 0)

    def test_a_refusal_of_the_story_is_a_round_from_the_build_stage(self):
        integration = Integration(refusal="gate:fail tests-green")
        lines = Lines()
        self.assertIsNone(IntegrateStoryUseCase(integration, lines).execute(IntegrateStoryCommand("S-1")))
        self.assertEqual((integration.rounds, integration.did[-1]), (1, "relink"))

    def test_a_lost_test_goes_back_to_the_integrate_stage_and_is_no_round(self):
        integration = Integration(refusal="gate:fail main-tests — a test lost its case", lost=[("T.java", ["x"])])
        IntegrateStoryUseCase(integration, Lines()).execute(IntegrateStoryCommand("S-1"))
        self.assertEqual(integration.did[:4], ["prepare", "gate", "session", "prepare"])

    def test_a_checkout_that_cannot_take_the_story_stops_for_a_person(self):
        integration = Integration(refusal="gate:fail checkout — dirty")
        self.assertEqual(IntegrateStoryUseCase(integration, Lines()).execute(IntegrateStoryCommand("S-1")), 1)
        self.assertEqual(integration.rounds, 0)


if __name__ == "__main__":
    unittest.main()
