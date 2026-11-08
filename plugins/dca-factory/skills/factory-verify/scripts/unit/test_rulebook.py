"""The rulebook (WP-166): every gate check carries its rules where it registers, every name the gate reports under
has one, every id is unique and of the scheme; a marked paragraph of a skill is an instructed rule placed in its
stage, a cited id no rule has is a problem — and `factory-cli.py --rules` shows it, generated, the plugin's own
rulebook holding."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.api.rules import pipeline_rules
from dca_factory.delivery.application.delivery.check_stage import CHECKS, check, chosen_stages
from dca_factory.delivery.application.delivery.pipeline_workflow import load as load_stages, workflow
from dca_factory.delivery.adapter.outgoing.workflow.rule_files import RuleFiles
from dca_factory.delivery.adapter.outgoing.workflow.stage_files import StageFiles
from dca_factory.delivery.domain.model.stage import HandOver, Role, Stage, StageName
from dca_factory.delivery.domain.model.workflow import DELIVERY, InconsistentWorkflow, MissingRole, Workflow, WorkflowName
from dca_factory.delivery.application.delivery import pipeline_rules as bound_rules
from dca_factory.delivery.domain.model.jump import RuleId, Target
from dca_factory.delivery.domain.model.workflow_rule import Outcome, OutcomeState, RulePart, RuleText, WorkflowRule
from dca_factory.infrastructure.rulebook import show_rulebook
from dca_factory.rulebook.adapter.outgoing.skills.skill_files import SkillFiles
from dca_factory.rulebook.application.show_rulebook import ShowRulebookQuery, ShowRulebookUseCase
from dca_factory.rulebook.adapter.outgoing.delivery.delivery_rules import (
    DeliveryFindings, DeliveryJournals, DeliveryRules)
from dca_factory.rulebook.domain.model.rule import Count, KindName
from dca_factory.rulebook.domain.model.runs import RouteReading, StoryJournal, story_run
from dca_factory.rulebook.adapter.incoming.cli.flow_svg import svg
from dca_factory.rulebook.application.show_rulebook import graph_model
from dca_factory.rulebook.domain.model import rule as book_rule
from dca_factory.rulebook.domain.model.rulebook import GateTime, KindOrder, OrderPlace, Rulebook, StageRow, Way

PACKAGE = os.path.join(support.SCRIPTS, "dca_factory")
SKILLS = os.path.normpath(os.path.join(support.SCRIPTS, "..", ".."))
#: A name the gate reports under, written as a literal where it is said.
SAID = re.compile(r"""(?:CheckName\(|\.(?:ok|fail|skip|note|wait)\()f?["']([a-z][a-z-]*)["']""")
#: Names the gate builds at run time: the tests' expectation, the profile's commands, the description's parts.
BUILT = {"tests-red", "tests-green", "architecture", "format", "compile", "product", "tech"}


def reported_names():
    """Every literal name the delivery context's gate reports under."""
    names = set()
    for top, _dirs, files in os.walk(os.path.join(PACKAGE, "delivery")):
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(top, name), encoding="utf-8") as handle:
                    names |= set(SAID.findall(handle.read()))
    return names


def plant(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


class RegisteredTest(unittest.TestCase):

    def test_every_check_carries_a_rule_and_every_id_is_unique(self):
        self.assertTrue(all(c.rules for c in CHECKS))
        ids = [r["id"] for r in pipeline_rules()]
        self.assertEqual(len(ids), len(set(ids)), sorted({i for i in ids if ids.count(i) > 1}))
        self.assertTrue(all(re.fullmatch(r"(GATE|RUN|STAGE)(-[A-Z0-9]+)+", i) for i in ids), ids)

    def test_every_rule_written_in_the_package_is_published(self):
        written = set()
        for top, dirs, files in os.walk(os.path.join(PACKAGE, "delivery")):
            dirs[:] = [d for d in dirs if d != "web"]   # the page shows rule ids as examples; it binds none
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(top, name), encoding="utf-8") as handle:
                        written |= set(re.findall(r'"((?:GATE|RUN)(?:-[A-Z0-9]+)+)"', handle.read()))
        published = {r["id"] for r in pipeline_rules() if r["bound"]}
        self.assertEqual([], sorted(written - published), "a module that binds rules is not imported by api/rules.py")
        self.assertEqual([], bound_rules.unbound(), "a rule's file that no code binds")

    def test_every_name_the_gate_reports_under_has_a_rule(self):
        covered = {name for r in pipeline_rules() for name in r["reports"]}
        missing = sorted((reported_names() | BUILT) - covered)
        self.assertEqual([], missing)

    def test_every_rule_says_when_why_and_an_outcome_where_it_is_written_and_where_it_is_bound(self):
        for found in pipeline_rules():
            self.assertTrue(os.path.isfile(os.path.join(support.SCRIPTS, found["source"])), found["source"])
            self.assertTrue(found["source"].endswith(f"/{found['id']}.md"), found["source"])
            if found["part"] == "told":
                # a told rule's words stand where a frame places them, or the reference says the rest of it
                self.assertTrue(found["told"] and (found["retired"] or found["placed"]), found["id"])
                if found["placed"]:
                    self.assertTrue(os.path.isfile(os.path.join(support.SCRIPTS, found["placed"]))
                                    or os.path.isfile(os.path.join(SKILLS, found["placed"])), found["placed"])
                continue
            self.assertTrue(found["when"] and found["why"] and found["outcomes"], found["id"])
            path, _, line = found["bound"].rpartition(":")
            self.assertTrue(os.path.isfile(os.path.join(PACKAGE, "..", path)) and line.isdigit(), found["bound"])

    def test_a_check_without_a_rule_and_a_stage_id_in_code_are_refused(self):
        with self.assertRaises(TypeError):
            check("story")   # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            check("story", rule="RUN-X-1")
        with self.assertRaises(ValueError):
            RuleId("STAGE")
        with self.assertRaises(ValueError):
            WorkflowRule(RuleId("GATE-X"), RulePart.CHECK, RuleText("w"), RuleText("y"))
        with self.assertRaises(ValueError):          # what a stage is told says something, and has no outcome
            WorkflowRule(RuleId("STAGE-PLAN-1"), RulePart.TOLD, RuleText(""), RuleText(""), told=RuleText(" "))
        with self.assertRaises(ValueError):
            WorkflowRule(RuleId("STAGE-PLAN-1"), RulePart.TOLD, RuleText(""), RuleText(""),
                         [Outcome(OutcomeState.FAIL, RuleText("f"))], told=RuleText("Plan."))
        with self.assertRaises(ValueError):
            chosen_stages("story", ("nowhere",), workflow())


class RuleFilesTest(unittest.TestCase):
    """The rules' repository over Markdown files: what is saved reads back the same, a file is named after its id,
    and a rule the code binds but no file holds stops the process that loads them."""

    def test_a_saved_rule_reads_back_the_same(self):
        rule = WorkflowRule(RuleId("RUN-X-1"), RulePart.DECISION, RuleText("w"), RuleText("y"),
                            [Outcome(OutcomeState.FAIL, RuleText('"quoted" both "ends"'),
                                     (Target("test"), Target("stop")))])
        with tempfile.TemporaryDirectory() as root:
            files = RuleFiles(os.path.join(root, "workflow", "rules"))
            back = files.save(rule)
            self.assertEqual((back.when, back.why, back.outcomes), (rule.when, rule.why, rule.outcomes))
            self.assertEqual("workflow/rules/run/RUN-X-1.md", back.written.value)
            self.assertEqual([back.id], [r.id for r in files.all()])
            files.delete_by_id(rule.id)
            self.assertIsNone(files.find_by_id(rule.id))

    def test_a_file_named_other_than_its_id_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {"run/RUN-X-1.md": "---\nid: RUN-X-2\nfail: f\n---\n"})
            with self.assertRaises(ValueError):
                RuleFiles(root).all()

    def test_a_bound_rule_without_its_file_stops_the_load(self):
        saved = dict(bound_rules.RULES)
        try:
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    bound_rules.load(RuleFiles(root))
        finally:
            bound_rules.RULES.clear()
            bound_rules.RULES.update(saved)


class StageFilesTest(unittest.TestCase):
    """The workflow's repository over Markdown files: the stages read back as saved, in their order; the workflow as
    a whole holds each name once and weighs only files its stages write."""

    def test_the_workflow_reads_back_the_same(self):
        with tempfile.TemporaryDirectory() as root:
            files = StageFiles(os.path.join(root, "workflow", "stages"))
            back = files.save(workflow())
            self.assertEqual(workflow().stages, back.stages)
            self.assertEqual(sorted(s.name.value + ".md" for s in back.stages),
                             sorted(os.listdir(os.path.join(root, "workflow", "stages"))))
            self.assertEqual("workflow/stages/plan.md", files.find_by_id(DELIVERY).written(StageName("plan")).value)
            self.assertIsNone(files.find_by_id(WorkflowName("other")))
            files.delete_by_id(DELIVERY)
            self.assertIsNone(files.find_by_id(DELIVERY))

    def test_a_file_named_other_than_its_stage_or_without_its_place_is_refused(self):
        for text in ("---\nname: plan\norder: 1\n---\n", "---\nname: build\n---\n"):
            with tempfile.TemporaryDirectory() as root:
                plant(root, {"build.md": text})
                with self.assertRaises(ValueError):
                    StageFiles(root).find_by_id(DELIVERY)

    def test_a_workflow_names_each_stage_once_and_weighs_what_its_stages_write(self):
        plan = Stage(StageName("plan"), HandOver("plan.md"))
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [plan, plan])
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [Stage(StageName("stop"))])
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [Stage(StageName("test"), HandOver("plan.md")), plan])
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [Stage(StageName("build"), sizes=(HandOver("build.md"),))])
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [])
        with self.assertRaises(InconsistentWorkflow):
            Workflow(DELIVERY, [Stage(StageName("a"), role=Role.JUDGES), Stage(StageName("b"), role=Role.JUDGES)])
        with self.assertRaises(MissingRole):
            Workflow(DELIVERY, [plan]).role(Role.JUDGES)
        self.assertEqual(workflow().role(Role.DELIVERS), StageName("document"))

    def test_the_rulebook_names_each_stage_by_its_file(self):
        view = show_rulebook(".").execute(ShowRulebookQuery())
        self.assertEqual([s.name.value for s in workflow().stages], [s["name"] for s in view["stages"]])
        self.assertTrue(all(s["source"] == f"workflow/stages/{s['name']}.md" and s["about"] for s in view["stages"]))

    def test_no_workflow_stops_the_load(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                load_stages(StageFiles(root))


class SkillsTest(unittest.TestCase):

    def book(self, root):
        return ShowRulebookUseCase(DeliveryRules(), SkillFiles(root), DeliveryFindings("."),
                                   DeliveryJournals(root)).execute(ShowRulebookQuery())

    def test_what_a_stage_is_told_comes_from_its_file_and_holds_at_its_stage(self):
        view = show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery())
        told = {r["id"]: r for r in view["rules"] if r["part"] == "instruction"}
        self.assertEqual(["build"], told["STAGE-BUILD-1"]["stages"])
        self.assertEqual("workflow/rules/stage/STAGE-BUILD-1.md", told["STAGE-BUILD-1"]["source"])
        self.assertEqual("workflow/stages/build.md", told["STAGE-BUILD-1"]["bound"])
        self.assertEqual("workflow/every-stage.md", told["STAGE-COMMON-1"]["bound"])
        self.assertEqual("factory-run/reference/file-contracts.md", told["STAGE-FILES-9"]["bound"])
        self.assertTrue(told["STAGE-BUILD-1"]["text"].startswith("Read the plan and the failing tests. Implement the "
                                                                 "smallest change"), told["STAGE-BUILD-1"]["text"])
        plan = next(s for s in view["flow"]["story"]["steps"] if s["stage"] == "plan")
        self.assertIn("STAGE-PLAN-9A", plan["told"])
        self.assertTrue(any(i.startswith("STAGE-COMMON-") for i in view["outside"]))
        self.assertTrue(any(r["kinds"] == ["task"] for r in told.values()))
        retired = {r["id"] for r in view["retired"]}
        self.assertIn("STAGE-BACKLOG-1", retired)
        self.assertNotIn("STAGE-FILES-9", retired)

    def test_a_marker_left_in_a_skill_and_a_cited_unknown_id_are_problems(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "factory-run/reference/file-contracts.md": "# Files\n\n<!-- rule: STAGE-COMMON-1 -->\nOther words.\n",
                "some-skill/SKILL.md": "See GATE-NO-SUCH and GATE-TESTS-KEPT.\n"})
            problems = "\n".join(self.book(root)["problems"])
            self.assertIn("STAGE-COMMON-1 is marked in factory-run/reference/file-contracts.md", problems)
            self.assertIn("never in a skill", problems)
            self.assertIn("some-skill/SKILL.md:1 cites GATE-NO-SUCH", problems)
            self.assertNotIn("GATE-TESTS-KEPT", problems)

    def test_the_plugins_own_rulebook_holds(self):
        view = show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery())
        self.assertEqual(os.path.normpath(SKILLS), os.path.normpath(view["skills"]))
        self.assertEqual([], view["problems"])


class FlowTest(unittest.TestCase):

    def test_an_outcome_says_where_the_story_goes_and_the_flow_draws_it(self):
        flow = show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery(kind="story"))["flow"]["story"]
        edges = {(e["source"], e["target"], e["rule"]) for e in flow["edges"]}
        self.assertIn(("build", "test", "RUN-BACK-1"), edges)
        self.assertIn(("judge", "build", "RUN-VERDICT-1"), edges)
        self.assertIn(("document", "plan", "GATE-ACCEPTANCE"), edges)
        self.assertIn(("integrate", "integrate", "GATE-MOVED"), edges)        # `again`: the stage itself
        with tempfile.TemporaryDirectory() as root:                           # goes on an outcome it does not say
            plant(root, {"run/RUN-X-1.md": "---\nid: RUN-X-1\npass: o\ngoes.fail: test\n---\n"})
            with self.assertRaises(ValueError):
                RuleFiles(root).all()

    def test_a_story_marks_the_rules_its_last_gate_runs_reported_and_counts_its_refusals(self):
        with tempfile.TemporaryDirectory() as root:
            evidence = os.path.join(root, ".dca-factory", "evidence", "s-1")
            plant(evidence, {
                "gate-build.101500.txt": "gate:pass 2 check(s) — story, tests-kept\ngate:fail suite — red\n"
                                         "gate:note stage build ran without x — a green run here does not cover them\n"
                                         "gate:fail story s-1 stage build\n",
                "journal.tsv": "2026-10-30T10:15:00Z\tgate\tbuild\texit=1\tfail=suite,tests-kept\tseq=1\n"
                               "2026-10-30T10:16:00Z\tgate\tbuild\texit=1\tfail=suite\tseq=2\n"})
            story = ShowRulebookUseCase(DeliveryRules(), SkillFiles(None), DeliveryFindings(root),
                                        DeliveryJournals(root)).execute(ShowRulebookQuery(story="s-1"))["story"]
            self.assertEqual([{"stage": "build", "state": "fail"}], story["fired"]["GATE-SUITE"])
            self.assertEqual([{"stage": "build", "state": "pass"}], story["fired"]["GATE-TESTS-KEPT"])
            self.assertNotIn("GATE-PLAN-FILES", story["fired"])
            self.assertEqual({"GATE-SUITE": 2, "GATE-TESTS-KEPT": 1}, story["refused"])
            self.assertEqual({"build": {"GATE-SUITE": 2, "GATE-TESTS-KEPT": 1}}, story["refused_at"])


def rule(rule_id, stages, *outcomes, part=book_rule.Part.DECISION):
    """A rule of the rulebook's own model: <outcomes> as (state, goes…)."""
    return book_rule.Rule(
        book_rule.RuleId(rule_id), part, tuple(book_rule.StageName(s) for s in stages), (), book_rule.Words("w"),
        tuple(book_rule.Outcome(book_rule.OutcomeState(state), book_rule.Words("s"),
                                tuple(book_rule.StageName(g) for g in goes)) for state, *goes in outcomes),
        book_rule.Words("y"), book_rule.Words(""), (), book_rule.Source("x.md"))


def row(name, gate):
    return StageRow(book_rule.StageName(name), (book_rule.KindName("story"),), GateTime(gate), OrderPlace.IN_ORDER,
                    book_rule.Words(""))


class GraphTest(unittest.TestCase):
    """The drawn flow comes from the rules alone (WP-172): a stage, a check or a `goes` changed in a file shows in the
    graph and the drawing with no change of code."""

    def book(self, stages, rules):
        return Rulebook(tuple(rules), tuple(row(n, g) for n, g in stages),
                        (KindOrder(book_rule.KindName("story"), tuple(book_rule.StageName(n) for n, _g in stages)),))

    def edges(self, graph):
        return {(e.source.value, e.target.value, e.way): {r.rule.value for r in e.rules} for e in graph.edges}

    STAGES = [("plan", "before"), ("test", "after"), ("build", "after"), ("judge", "none")]
    RULES = [rule("RUN-ROUNDS-1", ["test", "build"], ("fail", "again", "stop")),
             rule("RUN-BACK-1", ["build"], ("fail", "test")),
             rule("RUN-VERDICT-1", ["judge"], ("pass",), ("fail", "build", "stop")),
             rule("RUN-ROUTE-6", [], ("ask", "stop")),
             rule("GATE-TESTS-RED", ["test"], ("pass",), ("fail",), part=book_rule.Part.CHECK)]

    def test_each_outcome_is_an_edge_of_its_way(self):
        graph = self.book(self.STAGES, self.RULES).graph(book_rule.KindName("story"))
        edges = self.edges(graph)
        self.assertEqual({"RUN-ROUNDS-1"}, edges[("test", "test", Way.AGAIN)])
        self.assertEqual({"RUN-BACK-1"}, edges[("build", "test", Way.BACK)])
        self.assertEqual({"RUN-VERDICT-1"}, edges[("judge", "build", Way.BACK)])
        self.assertIn(("judge", "delivered", Way.ON), edges)                 # the plain way on, to the end
        self.assertIn(("plan", "test", Way.ON), edges)
        anywhere = {(e.target.value, e.way) for e in graph.anywhere}
        self.assertIn(("waits", Way.WAITS), anywhere)                          # `ask` waits for a person, not stop
        self.assertEqual([], [p.said.value for p in self.book(self.STAGES, self.RULES).unrounded()])

    def test_a_new_stage_a_new_way_back_and_a_stage_without_a_round_show_without_code(self):
        stages = self.STAGES[:3] + [("review", "after")] + self.STAGES[3:]
        rules = self.RULES + [rule("RUN-REVIEW-1", ["review"], ("fail", "plan"))]
        book = self.book(stages, rules)
        graph = book.graph(book_rule.KindName("story"))
        self.assertEqual({"RUN-REVIEW-1"}, self.edges(graph)[("review", "plan", Way.BACK)])
        problems = [p.said.value for p in book.unrounded()]
        self.assertEqual(1, len(problems))
        self.assertIn("review has a gate after it", problems[0])
        drawn = svg(graph_model(graph), "story")
        self.assertIn('data-stage="review"', drawn)
        self.assertIn('data-source="review" data-target="plan" data-way="back"', drawn)
        self.assertIn('data-gate="gate-after:review"', drawn)

    def test_the_plugins_own_flow_has_a_round_at_every_gated_step(self):
        flow = show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery(kind="story"))["flow"]["story"]
        graph = flow["graph"]
        again = {e["source"] for e in graph["edges"] if e["way"] == "again" and
                 any(r["rule"] == "RUN-ROUNDS-1" for r in e["rules"])}
        gated = {s["stage"] for s in graph["steps"] if s["gate"] == "after"}
        self.assertEqual(gated, again)
        self.assertTrue(any(e["way"] == "waits" for e in graph["every_gate"]), graph["every_gate"])
        backs = {(e["source"], e["target"]) for e in graph["edges"] if e["way"] == "back"}
        self.assertTrue({("build", "test"), ("judge", "build"), ("document", "plan")} <= backs, backs)


class CliTest(unittest.TestCase):

    def cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(support.SCRIPTS, "factory-cli.py"), "--rules", *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=tempfile.gettempdir())

    def test_the_rulebook_is_generated_as_markdown_and_json_and_checks_itself(self):
        checked = self.cli("--check")
        self.assertEqual(0, checked.returncode, checked.stderr)
        shown = self.cli()
        self.assertTrue(shown.stdout.startswith("# The factory's rules"), shown.stdout[:200])
        self.assertIn("### GATE-TESTS-KEPT", shown.stdout)
        view = json.loads(self.cli("--format", "json", "--kind", "task").stdout)
        self.assertEqual(["task"], list(view["flow"]))
        self.assertEqual(["plan", "build", "tidy", "judge", "document", "integrate"],
                         [s["stage"] for s in view["flow"]["task"]["steps"]])
        self.assertTrue(all(not r["kinds"] or "task" in r["kinds"] for r in view["rules"]))
        self.assertTrue(view["flow"]["task"]["svg"].startswith("<svg"))
        self.assertEqual(["plan", "build", "tidy", "judge", "document", "integrate"],
                         [t["stage"] for t in view["flow"]["task"]["track"]["tiles"]])
        drawn = self.cli("--format", "svg", "--kind", "journey").stdout
        self.assertTrue(drawn.startswith("<svg"), drawn[:200])
        self.assertIn('data-stage="judge"', drawn)
        self.assertNotIn('data-stage="build"', drawn)


if __name__ == "__main__":
    unittest.main()


class TrackTest(unittest.TestCase):
    """The rules page's track (WP-194): one line per pair of stages, read off the rules' `goes` — never a list in the
    page —; a repeat of a stage is its tile's round, a restart its tile's note; the journal's route read as the runner
    wrote it, an older journal from the order of its gates."""

    def setUp(self):
        rules = DeliveryRules()
        self.book = Rulebook(rules.rules(), rules.rows(), rules.orders())

    def ways(self, kind):
        return {(w.source.value, w.target.value): (w.cost.value, [r.value for r in w.rules], w.reason.value)
                for w in self.book.track(KindName(kind), Count(3)).ways}

    def test_the_story_kind_has_six_ways_back_one_per_pair(self):
        # a red proof refused after build or tidy is the stage's own change — a round, not a restart (RUN-ROUTE-5 is)
        # the runner's decision first — its reason labels the line
        self.assertEqual({("build", "test"): ("round", ["RUN-BACK-1", "GATE-RED-PROOF"],
                                              "a test cannot pass · a test changed since its red proof"),
                          ("tidy", "test"): ("round", ["GATE-RED-PROOF"], "a test changed since its red proof"),
                          ("judge", "build"): ("round", ["RUN-VERDICT-1"], "changes requested"),
                          ("judge", "test"): ("round", ["RUN-VERDICT-1"], "changes requested"),
                          ("integrate", "build"): ("round", ["RUN-INTEGRATE-1"], "the main line refuses"),
                          ("delivered", "plan"): ("free", ["GATE-ACCEPTANCE"], "a correction at acceptance")},
                         self.ways("story"))

    def test_a_task_has_no_test_tile_and_no_acceptance(self):
        track = self.book.track(KindName("task"), Count(3))
        self.assertNotIn("test", [t.stage.value for t in track.tiles])
        self.assertFalse(track.accepted())
        self.assertEqual({("judge", "build"), ("integrate", "build")}, set(self.ways("task")))

    def test_a_restart_is_a_note_on_its_tile_and_a_repeat_its_round(self):
        tiles = {t.stage.value: t for t in self.book.track(KindName("story"), Count(3)).tiles}
        self.assertEqual({"RUN-STANDING-2", "RUN-ROUTE-7"}, {r.value for r in tiles["plan"].restarts})
        self.assertEqual({"RUN-ROUTE-5"}, {r.value for r in tiles["test"].restarts})
        self.assertEqual(("rounds", "once", "decides"),
                         (tiles["build"].turn.value, tiles["plan"].turn.value, tiles["judge"].turn.value))

    def journal(self, root, lines):
        plant(os.path.join(root, ".dca-factory", "evidence", "s-1"), {"journal.tsv": "".join(
            f"2026-11-0{1 + n // 50}T10:{n % 50:02d}:00Z\t{line}\tseq={n + 1}\n" for n, line in enumerate(lines))})
        [found] = DeliveryJournals(root).journals()
        return story_run(found, self.book.track(KindName("story"), Count(3)))

    def test_the_runner_s_own_lines_say_where_the_story_went(self):
        with tempfile.TemporaryDirectory() as root:
            run = self.journal(root, ["gate\tplan\texit=0\tby=runner", "stage-start\tbuilder\tstages=plan,test,build,tidy",
                                      "gate\ttest\texit=1\tfail=spec-delta\tby=builder", "gate\tbuild\texit=0\tby=runner",
                                      "stage-start\tverifier", "jump\ttest\tfrom=judge\trule=RUN-VERDICT-1",
                                      "gate\tbuild\texit=1\tfail=suite\tby=runner",
                                      "restart\ttest\trule=RUN-ROUTE-5\treason=test-changed", "gate\tbuild\texit=0\tby=runner"])
            self.assertEqual(RouteReading.JOURNAL, run.reading)
            self.assertEqual([("judge", "test", 1)], [(w.source.value, w.target.value, w.times.value) for w in run.ways])
            self.assertEqual({"test": 1}, {r.stage.value: r.times.value for r in run.restarts})
            stages = {s.stage.value: s for s in run.stages}
            self.assertEqual((1, 0), (stages["test"].tries.value, stages["test"].refused.value))   # inside, not between
            self.assertEqual(1, stages["build"].refused.value)
            self.assertEqual("build", run.last.value)

    def test_an_older_journal_is_read_from_the_order_of_the_runner_s_gates(self):
        with tempfile.TemporaryDirectory() as root:
            run = self.journal(root, ["gate\tplan\texit=0", "gate\tbuild\texit=0\tby=runner", "stage-start\tverifier",
                                      "gate\tbuild\texit=0\tby=runner", "stage-start\tverifier",
                                      "gate\tplan\texit=0\tby=runner"])
            self.assertEqual(RouteReading.GATE_ORDER, run.reading)
            self.assertEqual([("judge", "build", 1)], [(w.source.value, w.target.value, w.times.value) for w in run.ways])
            self.assertEqual({"plan": 1}, {r.stage.value: r.times.value for r in run.restarts})   # no way back to plan

    def test_the_project_s_refusals_are_counted_per_rule(self):
        with tempfile.TemporaryDirectory() as root:
            plant(os.path.join(root, ".dca-factory", "evidence"), {
                "a/journal.tsv": "2026-11-01T10:00:00Z\tgate\tbuild\texit=1\tfail=suite\tby=runner\tseq=1\n",
                "b/journal.tsv": "2026-11-02T10:00:00Z\tgate\tbuild\texit=1\tfail=suite\tby=builder\tseq=1\n"
                                 "2026-11-03T10:00:00Z\tgate\ttidy\texit=1\tby=runner\tseq=2\n"})
            view = show_rulebook(root).execute(ShowRulebookQuery())["refusals"]
            self.assertEqual(2, view["rules"]["GATE-SUITE"]["times"])
            self.assertEqual({"a": 1, "b": 1}, view["rules"]["GATE-SUITE"]["stories"])
            self.assertEqual("2026-11-02T10:00:00Z", view["rules"]["GATE-SUITE"]["last"])
            self.assertEqual(1, view["unnamed"])
