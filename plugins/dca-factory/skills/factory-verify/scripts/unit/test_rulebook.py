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
from dca_factory.delivery.application.delivery.check_stage import CHECKS, check
from dca_factory.delivery.application.delivery.pipeline_rules import rule
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
        self.assertTrue(all(re.fullmatch(r"(GATE|RUN)(-[A-Z0-9]+)+", i) for i in ids), ids)

    def test_every_rule_written_in_the_package_is_published(self):
        written = set()
        for top, _dirs, files in os.walk(os.path.join(PACKAGE, "delivery")):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(top, name), encoding="utf-8") as handle:
                        written |= set(re.findall(r'rule\(\s*"((?:GATE|RUN)(?:-[A-Z0-9]+)+)"', handle.read()))
        published = {r["id"] for r in pipeline_rules()}
        self.assertEqual([], sorted(written - published), "a module that registers rules is not imported by api/rules.py")

    def test_every_name_the_gate_reports_under_has_a_rule(self):
        covered = {name for r in pipeline_rules() for name in r["reports"]}
        missing = sorted((reported_names() | BUILT) - covered)
        self.assertEqual([], missing)

    def test_every_rule_says_when_why_and_an_outcome_and_where_it_is_written(self):
        for found in pipeline_rules():
            self.assertTrue(found["when"] and found["why"] and found["outcomes"], found["id"])
            path, _, line = found["source"].rpartition(":")
            self.assertTrue(os.path.isfile(os.path.join(PACKAGE, "..", path)) and line.isdigit(), found["source"])

    def test_a_check_without_a_rule_and_a_stage_id_in_code_are_refused(self):
        with self.assertRaises(TypeError):
            check("story")   # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            check("story", rule=rule("RUN-X-1", "w", "y", ok="o"))
        with self.assertRaises(ValueError):
            rule("STAGE-PLAN-1", "w", "y", ok="o")
        with self.assertRaises(ValueError):
            rule("GATE-X", "w", "y")


class SkillsTest(unittest.TestCase):

    def book(self, root):
        return ShowRulebookUseCase(DeliveryRules(), SkillFiles(root), DeliveryFindings(".")).execute(ShowRulebookQuery())

    def test_a_marked_paragraph_is_a_rule_told_at_its_stage(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "factory-run/reference/stage-common.md": "# Common\n\n<!-- rule: STAGE-COMMON-1 -->\nEvery stage "
                                                         "reads the story.\n",
                "stage-plan/SKILL.md": "## Do\n\n<!-- rule: STAGE-PLAN-9A -->\n9a. **Find what shows.** A scenario\n"
                                       "that holds stays.\n\nNext paragraph.\n\n## Task mode\n\n"
                                       "<!-- rule: STAGE-PLAN-TASK -->\nA task plans no test.\n"})
            view = self.book(root)
            told = {r["id"]: r for r in view["rules"] if r["part"] == "instruction"}
            self.assertEqual("Find what shows. A scenario that holds stays.", told["STAGE-PLAN-9A"]["text"])
            self.assertEqual(["plan"], told["STAGE-PLAN-9A"]["stages"])
            self.assertEqual("stage-plan/SKILL.md:4", told["STAGE-PLAN-9A"]["source"])
            plan = next(s for s in view["flow"]["story"]["steps"] if s["stage"] == "plan")
            self.assertEqual(["STAGE-PLAN-9A"], plan["told"])
            self.assertIn("STAGE-COMMON-1", view["outside"])
            self.assertEqual(["task"], told["STAGE-PLAN-TASK"]["kinds"])
            self.assertNotIn("STAGE-PLAN-TASK", plan["told"])
            self.assertEqual([], view["problems"])

    def test_an_id_used_twice_a_cited_unknown_id_and_an_unknown_stage_are_problems(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "factory-run/reference/stage-common.md": "<!-- rule: STAGE-COMMON-1 -->\nOne.\n\n"
                                                         "<!-- rule: STAGE-COMMON-1 -->\nTwo.\n",
                "stage-test/SKILL.md": "See GATE-NO-SUCH and GATE-TESTS-KEPT.\n\n<!-- rule: STAGE-TESTX-1 -->\nX.\n"})
            problems = "\n".join(self.book(root)["problems"])
            self.assertIn("STAGE-COMMON-1 is used 2 times", problems)
            self.assertIn("stage-test/SKILL.md:1 cites GATE-NO-SUCH", problems)
            self.assertNotIn("GATE-TESTS-KEPT", problems)
            self.assertIn("STAGE-TESTX-1 names no stage testx", problems)

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
        with self.assertRaises(ValueError):
            rule("RUN-X-1", "w", "y", ok="o", goes={"fail": "test"})          # goes on an outcome it does not say

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
