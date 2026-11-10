"""Stage rules say why, in general words, and can be left out on a bench: every told rule's `why:` read and written
back, one without it a rulebook problem, `why: unknown` information only, and a told-rule group the profile's
`ablate:` leaves out of every brief."""

import os
import re
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.workflow.rule_files import FOLDER, RuleFiles
from dca_factory.delivery.domain.model.jump import RuleId
from dca_factory.delivery.domain.model.stage import StageName
from dca_factory.delivery.domain.model.workflow_rule import RuleGroup, RulePart, RuleText, WorkflowRule
from dca_factory.infrastructure.rulebook import show_rulebook
from dca_factory.rulebook.application.show_rulebook import ShowRulebookQuery

#: What a `why:` may never name: a work package, a story id, a date, a version.
SPECIFIC = re.compile(r"\bWP-\d+|\bSTORY-\d+|\b20\d\d-\d\d-\d\d\b|\b\d+\.\d+\.\d+\b|TODO #\d+")


def told(why, stages=("plan",), section="Do"):
    return WorkflowRule.restore(RuleId("STAGE-PLAN-99"), RulePart.TOLD, RuleText(""), RuleText(why), (), (),
                                [StageName(s) for s in stages], [], None, None, RuleText("99. **Do it.**"),
                                RuleText(section), None, None)


class WhyTest(unittest.TestCase):

    def test_every_stage_rule_says_why_in_general_words(self):
        rules = [r for r in RuleFiles().all() if r.part is RulePart.TOLD and r.retired is None]
        self.assertTrue(rules)
        self.assertEqual([r.id.value for r in rules if not r.why.value], [])
        self.assertEqual([r.id.value for r in rules if SPECIFIC.search(r.why.value)], [])

    def test_a_why_reads_back_as_written(self):
        with tempfile.TemporaryDirectory() as folder:
            files = RuleFiles(folder)
            saved = files.save(told("a stage guessed what the story left open"))
            self.assertEqual(saved.why.value, "a stage guessed what the story left open")
            self.assertIn("\nwhy: a stage guessed what the story left open\n",
                          open(os.path.join(folder, "stage", "STAGE-PLAN-99.md"), encoding="utf-8").read())

    def test_the_rulebook_names_a_told_rule_without_why_and_lists_unknown_ones_as_information(self):
        view = show_rulebook(os.path.dirname(os.path.dirname(FOLDER))).execute(ShowRulebookQuery(None, None, None))
        self.assertFalse([p for p in view["problems"] if "says no `why:`" in p])
        self.assertIsInstance(view["unexplained"], list)


class AblationTest(unittest.TestCase):

    def test_a_group_is_one_section_of_one_stage_or_of_what_every_stage_is_told(self):
        self.assertTrue(RuleGroup(StageName("plan"), RuleText("do")).covers(told("x")))
        self.assertFalse(RuleGroup(StageName("plan"), RuleText("Do not")).covers(told("x")))
        self.assertFalse(RuleGroup(StageName("test"), RuleText("Do")).covers(told("x")))
        self.assertTrue(RuleGroup(None, RuleText("Do")).covers(told("x", stages=())))
        self.assertFalse(RuleGroup(None, RuleText("Do")).covers(told("x")))

    def test_the_profiles_ablate_leaves_a_group_out_of_the_brief(self):
        from dca_factory.infrastructure import gate  # noqa: F401 — loads the workflow and its rules
        from dca_factory.delivery.application.delivery.show_brief import ShowBriefQuery, ShowBriefUseCase
        from dca_factory.delivery.domain.model.stage import StoryKind
        from dca_factory.delivery.domain.model.story import StoryId

        class Stories:
            def get(self, story):
                return type("S", (), {"kind": StoryKind.STORY})()

        class Profile:
            def __init__(self, ablate):
                self.ablate = ablate

            def profile(self):
                return {"ablate": self.ablate} if self.ablate else {}

        def brief(ablate):
            said = ShowBriefUseCase(Stories(), Profile(ablate)).execute(ShowBriefQuery(StoryId("S-1"), StageName("plan")))
            return said.said.value

        whole, without = brief(""), brief("plan:Do not, every:nothing")
        self.assertIn("Do not renumber or rename the criterion keys", whole)
        self.assertNotIn("Do not renumber or rename the criterion keys", without)
        self.assertIn("Announce a change to what judges the story", without)


if __name__ == "__main__":
    unittest.main()
