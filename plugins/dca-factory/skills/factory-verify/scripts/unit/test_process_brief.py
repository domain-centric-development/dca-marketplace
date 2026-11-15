"""A process beside the stages — the reviewers — is told what reaches it by name (`processes:`), and nothing else of
what every stage is told (WP-220 lever 1)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.delivery import pass_actions, process_checks, stage_checks  # noqa: F401
from dca_factory.delivery.application.delivery.pipeline_rules import RULES
from dca_factory.delivery.application.delivery.pipeline_workflow import workflow
from dca_factory.delivery.domain.model.workflow_rule import ProcessName
from dca_factory.delivery.domain.service.stage_brief import StageBrief


class ProcessBriefTest(unittest.TestCase):

    def test_the_review_brief_holds_the_rules_that_name_the_process_and_no_other(self):
        told = StageBrief(workflow()).told_to(ProcessName("review"), list(RULES.values())).value
        named = [rule.id.value for rule in RULES.values() if ProcessName("review") in rule.processes]
        self.assertIn("STAGE-COMMON-24", named)
        for rule_id in named:
            self.assertIn(f"<!-- rule: {rule_id} -->", told)
        self.assertEqual(len(named), told.count("<!-- rule: "))

    def test_it_is_a_fraction_of_what_every_stage_is_told(self):
        brief = StageBrief(workflow())
        review = brief.told_to(ProcessName("review"), list(RULES.values())).value
        every = brief.every_stage(list(RULES.values())).value
        self.assertLess(len(review) * 10, len(every))

    def test_a_process_no_rule_names_is_told_nothing(self):
        self.assertEqual("", StageBrief(workflow()).told_to(ProcessName("nobody"), list(RULES.values())).value)


if __name__ == "__main__":
    unittest.main()
