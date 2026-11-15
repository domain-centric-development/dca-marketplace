"""A rule switched off, not deleted: `state: disabled` with `disabled: <date> — <why>` reads and writes back, no brief
tells a disabled told rule, no gate runs a check whose rules are all disabled, the rulebook lists disabled rules apart
with the stories delivered since, and a runner's decision cannot be disabled."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.delivery import pass_actions, process_checks, stage_checks  # noqa: F401
from dca_factory.delivery.application.delivery.check_stage import CHECKS, judging, switched_off
from dca_factory.delivery.application.delivery.pipeline_rules import RULES
from dca_factory.delivery.application.delivery.pipeline_workflow import workflow
from dca_factory.delivery.adapter.outgoing.workflow.rule_files import RuleFiles
from dca_factory.delivery.domain.model.jump import RuleId
from dca_factory.delivery.domain.model.stage import StageName, StoryKind
from dca_factory.delivery.domain.model.workflow_rule import RulePart, RuleText, WorkflowRule
from dca_factory.delivery.domain.service.stage_brief import StageBrief
from dca_factory.rulebook.domain.model.rule import (
    Count, Outcome, OutcomeState, Part, Rule, RuleId as BookId, RuleState, Source, Words)
from dca_factory.rulebook.domain.model.rulebook import Rulebook
from dca_factory.rulebook.domain.model.runs import JournalLine, JournalLineKind, Journals, StoryJournal
from dca_factory.rulebook.domain.model.rule import Moment, StageName as BookStage

SINCE = "2026-11-15 — never acted; bench shared-opus-medium-0.0.0-a"


def disabled(rule):
    """<rule> as its file would read with `state: disabled`."""
    return WorkflowRule.restore(rule.id, rule.part, rule.when, rule.why, rule.outcomes, rule.reports, rule.stages,
                                rule.kinds, rule.retired, rule.written, rule.told, rule.section, rule.see, rule.order,
                                rule.title, rule.restart, rule.processes, RuleText(SINCE))


class DisabledFileTest(unittest.TestCase):

    def test_a_disabled_rule_reads_back_and_is_in_force_nowhere(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = RuleFiles(folder).save(disabled(RULES["STAGE-BUILD-6"]))
            self.assertEqual(SINCE, saved.disabled.value)
            self.assertFalse(saved.in_force)
            self.assertIn("state: disabled", RuleFiles.text(saved))
            gate = RuleFiles(folder).save(disabled(RULES["GATE-RED-PROOF"]))
            self.assertEqual(SINCE, gate.disabled.value)
        self.assertTrue(RULES["STAGE-BUILD-6"].in_force)

    def test_state_and_reason_go_together_and_the_reason_starts_with_a_day(self):
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, "stage"))

            def written(front):
                path = os.path.join(folder, "stage", "STAGE-PLAN-99.md")
                with open(path, "w", encoding="utf-8") as out:
                    out.write(f"---\nid: STAGE-PLAN-99\npart: told\nwhy: unknown\nstages:\n- plan\n{front}---\n\n"
                              f"# STAGE-PLAN-99\n\nDo it.\n")
                return RuleFiles(folder)._read(path)
            self.assertTrue(written("").in_force)
            self.assertTrue(written("state: active\n").in_force)
            self.assertFalse(written(f"state: disabled\ndisabled: {SINCE}\n").in_force)
            for wrong in ("state: disabled\n", f"disabled: {SINCE}\n", "state: off\n",
                          "state: disabled\ndisabled: never acted\n"):
                with self.assertRaises(ValueError, msg=wrong):
                    written(wrong)


class DisabledInForceTest(unittest.TestCase):

    def setUp(self):
        self.kept = dict(RULES)

    def tearDown(self):
        RULES.clear()
        RULES.update(self.kept)

    def test_no_brief_tells_a_disabled_told_rule(self):
        RULES["STAGE-BUILD-6"] = disabled(RULES["STAGE-BUILD-6"])
        told = [t.rule.value for t in StageBrief(workflow()).of(
            StageName("build"), StoryKind.STORY, list(RULES.values()),
            [RuleId(r) for r in judging("build", StoryKind.STORY)], ()).told]
        self.assertNotIn("STAGE-BUILD-6", told)
        self.assertIn("STAGE-BUILD-5", told)

    def test_a_check_whose_rules_are_all_disabled_does_not_run_and_is_no_gate_line(self):
        entry = next(c for c in CHECKS if c.name == "red-proof")
        self.assertFalse(switched_off(entry))
        RULES["GATE-RED-PROOF"] = disabled(RULES["GATE-RED-PROOF"])
        self.assertTrue(switched_off(entry))
        self.assertNotIn("GATE-RED-PROOF", judging("build", StoryKind.STORY))
        # a check with several rules runs while one of them is in force
        several = next(c for c in CHECKS if len(c.rules) > 1)
        RULES[several.rules[0].rule] = disabled(RULES[several.rules[0].rule])
        self.assertFalse(switched_off(several))


def book_rule(rule_id, state, part=Part.CHECK, said=""):
    return Rule(BookId(rule_id), part, (), (), Words("when"), (Outcome(OutcomeState.FAIL, Words("no")),),
                Words("why"), Words(""), (), Source(f"{rule_id}.md"), state, Source("code.py:1"), Words("title"),
                disabled=Words(said))


class DisabledRulebookTest(unittest.TestCase):

    def test_stories_delivered_since_a_day_count_each_story_once(self):
        def journal(story, *days):
            return StoryJournal(Words(story), None, tuple(
                JournalLine(JournalLineKind.DELIVERED, Moment(f"{d}T10:00:00Z"), BookStage("document")) for d in days))
        journals = Journals((journal("a", "2026-11-14"), journal("b", "2026-11-15", "2026-11-16"),
                             journal("c", "2026-11-20"), StoryJournal(Words("d"), None, ())))
        self.assertEqual(Count(2), journals.delivered_since(Moment("2026-11-15")))
        self.assertEqual(Count(3), journals.delivered_since(Moment("2026-11-01")))

    def test_a_disabled_runner_decision_is_a_problem_a_disabled_check_is_not(self):
        rules = (book_rule("GATE-SOME", RuleState.DISABLED, said=SINCE),
                 book_rule("RUN-SOME-1", RuleState.DISABLED, Part.DECISION, SINCE))
        problems = " ".join(p.said.value for p in Rulebook(rules, (), ()).problems(()))
        self.assertIn("RUN-SOME-1 is disabled", problems)
        self.assertNotIn("GATE-SOME", problems)
        self.assertEqual(Moment("2026-11-15"), rules[0].disabled_since)
        self.assertEqual((), Rulebook(rules, (), ()).active())


if __name__ == "__main__":
    unittest.main()
