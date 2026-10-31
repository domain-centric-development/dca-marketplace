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
from dca_factory.delivery.domain.model.stage import HandOver, Stage, StageName
from dca_factory.delivery.domain.model.workflow import DELIVERY, Workflow, WorkflowName
from dca_factory.delivery.application.delivery import pipeline_rules as bound_rules
from dca_factory.delivery.domain.model.jump import RuleId, Target
from dca_factory.delivery.domain.model.workflow_rule import Outcome, OutcomeState, RulePart, RuleText, WorkflowRule
from dca_factory.infrastructure.rulebook import show_rulebook
from dca_factory.rulebook.adapter.outgoing.skills.skill_files import SkillFiles
from dca_factory.rulebook.application.show_rulebook import ShowRulebookQuery, ShowRulebookUseCase
from dca_factory.rulebook.adapter.outgoing.delivery.delivery_rules import DeliveryFindings, DeliveryRules

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
        for top, _dirs, files in os.walk(os.path.join(PACKAGE, "delivery")):
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
                self.assertTrue(found["told"] and (found["retired"] or found["marked"]), found["id"])
                if found["marked"]:
                    self.assertTrue(os.path.isfile(os.path.join(SKILLS, found["marked"])), found["marked"])
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
        with self.assertRaises(ValueError):
            Workflow(DELIVERY, [plan, plan])
        with self.assertRaises(ValueError):
            Workflow(DELIVERY, [Stage(StageName("stop"))])
        with self.assertRaises(ValueError):
            Workflow(DELIVERY, [Stage(StageName("test"), HandOver("plan.md")), plan])
        with self.assertRaises(ValueError):
            Workflow(DELIVERY, [Stage(StageName("build"), sizes=(HandOver("build.md"),))])
        with self.assertRaises(ValueError):
            Workflow(DELIVERY, [])

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
        return ShowRulebookUseCase(DeliveryRules(), SkillFiles(root), DeliveryFindings(".")).execute(ShowRulebookQuery())

    def test_what_a_stage_is_told_comes_from_its_file_and_holds_at_its_stage(self):
        view = show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery())
        told = {r["id"]: r for r in view["rules"] if r["part"] == "instruction"}
        self.assertEqual(["build"], told["STAGE-BUILD-1"]["stages"])
        self.assertEqual("workflow/rules/stage/STAGE-BUILD-1.md", told["STAGE-BUILD-1"]["source"])
        self.assertEqual("stage-build/SKILL.md", told["STAGE-BUILD-1"]["bound"])
        self.assertTrue(told["STAGE-BUILD-1"]["text"].startswith("Read the plan and the failing tests. Implement the "
                                                                 "smallest change"), told["STAGE-BUILD-1"]["text"])
        plan = next(s for s in view["flow"]["story"]["steps"] if s["stage"] == "plan")
        self.assertIn("STAGE-PLAN-9A", plan["told"])
        self.assertTrue(any(i.startswith("STAGE-COMMON-") for i in view["outside"]))
        self.assertTrue(any(r["kinds"] == ["task"] for r in told.values()))
        retired = {r["id"] for r in view["retired"]}
        self.assertIn("STAGE-BACKLOG-1", retired)
        self.assertNotIn("STAGE-FILES-9", retired)

    def test_a_skills_words_apart_from_its_file_a_marker_without_file_and_a_cited_unknown_id_are_problems(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "factory-run/reference/stage-common.md": "# Common\n\n<!-- rule: STAGE-COMMON-1 -->\nOther words.\n\n"
                                                         "<!-- rule: STAGE-COMMON-1 -->\nTwice.\n",
                "stage-test/SKILL.md": "See GATE-NO-SUCH and GATE-TESTS-KEPT.\n\n<!-- rule: STAGE-TESTX-1 -->\nX.\n"})
            problems = "\n".join(self.book(root)["problems"])
            self.assertIn("STAGE-COMMON-1: the words in", problems)
            self.assertIn("STAGE-COMMON-1 is marked twice", problems)
            self.assertIn("STAGE-TESTX-1 is marked in", problems)
            self.assertIn("stage-test/SKILL.md:1 cites GATE-NO-SUCH", problems)
            self.assertNotIn("GATE-TESTS-KEPT", problems)
            self.assertIn("STAGE-BUILD-1: its file says stage-build/SKILL.md carries its words", problems)

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
            story = ShowRulebookUseCase(DeliveryRules(), SkillFiles(None), DeliveryFindings(root)).execute(
                ShowRulebookQuery(story="s-1"))["story"]
            self.assertEqual([{"stage": "build", "state": "fail"}], story["fired"]["GATE-SUITE"])
            self.assertEqual([{"stage": "build", "state": "pass"}], story["fired"]["GATE-TESTS-KEPT"])
            self.assertNotIn("GATE-PLAN-FILES", story["fired"])
            self.assertEqual({"GATE-SUITE": 2, "GATE-TESTS-KEPT": 1}, story["refused"])


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


if __name__ == "__main__":
    unittest.main()
