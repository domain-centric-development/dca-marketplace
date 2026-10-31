"""A stage's brief: what it is told for one story, decided over the workflow and the rules."""

import os
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.delivery import pass_actions, process_checks, stage_checks  # noqa: F401
from dca_factory.delivery.application.delivery.check_stage import judging
from dca_factory.delivery.application.delivery.pipeline_rules import RULES
from dca_factory.delivery.application.delivery.pipeline_workflow import workflow
from dca_factory.delivery.adapter.incoming.cli.brief_view import brief_model, markdown
from dca_factory.delivery.domain.model.jump import RuleId
from dca_factory.delivery.domain.model.stack_profile import SkillName
from dca_factory.delivery.domain.model.stage import StageName, StoryKind
from dca_factory.delivery.domain.model.workflow_rule import RulePart
from dca_factory.delivery.domain.service.stage_brief import Carrier, CarrierRole, expanded, StageBrief


SKILLS = os.path.normpath(os.path.join(support.SCRIPTS, "..", ".."))


def brief(stage, kind=StoryKind.STORY, carriers=()):
    return StageBrief(workflow()).of(StageName(stage), kind, list(RULES.values()),
                                     [RuleId(r) for r in judging(stage, kind)], carriers)


class StageBriefTest(unittest.TestCase):

    def test_a_stage_is_told_every_stages_rules_first_then_its_own_then_what_no_frame_places(self):
        told = [t.rule.value for t in brief("build").told]
        own = [r for r in told if r.startswith("STAGE-BUILD-")]
        self.assertTrue(told[0].startswith("STAGE-COMMON-"), told[:3])
        self.assertLess(told.index("STAGE-COMMON-1"), told.index(own[0]))
        self.assertGreater(min(told.index(r) for r in told if r.startswith("STAGE-FILES-")), told.index(own[-1]))
        self.assertEqual(own[:3], ["STAGE-BUILD-1", "STAGE-BUILD-1A", "STAGE-BUILD-2"])
        self.assertFalse([r for r in told if r.startswith(("STAGE-PLAN-", "STAGE-TEST-"))])

    def test_a_kind_hears_its_own_mode_and_no_other(self):
        story = {t.rule.value for t in brief("plan").told}
        task = {t.rule.value for t in brief("plan", StoryKind.TASK).told}
        moded = {r.id.value for r in RULES.values() if r.kinds and StageName("plan") in r.stages}
        self.assertTrue(moded)
        self.assertFalse(story & {r for r in moded if StoryKind.TASK in RULES[r].kinds})
        self.assertTrue(task & {r for r in moded if StoryKind.TASK in RULES[r].kinds})

    def test_the_gate_rules_it_is_measured_by_are_its_stages_checks_for_its_kind(self):
        build = [m.rule.value for m in brief("build").measured]
        self.assertIn("GATE-RED-PROOF", build)
        self.assertNotIn("GATE-HAPPY-PATH", build)
        self.assertIn("GATE-HAPPY-PATH", [m.rule.value for m in brief("plan").measured])
        self.assertEqual((), brief("judge").measured)       # the judge has no gate of its own

    def test_a_stage_the_kind_does_not_run_or_the_workflow_lacks_has_no_brief(self):
        with self.assertRaises(ValueError):
            brief("build", StoryKind.JOURNEY)
        with self.assertRaises(ValueError):
            brief("nowhere")

    def test_the_same_story_and_stage_give_the_same_brief_and_its_words_as_written(self):
        carriers = (Carrier(CarrierRole.CRAFT, SkillName("dca-modelling")),)
        first, second = brief("test", carriers=carriers), brief("test", carriers=carriers)
        self.assertEqual(first, second)
        text = markdown(first)
        self.assertEqual(text, markdown(second))
        self.assertIn("- craft: the `dca-modelling` skill", text)
        self.assertIn(RULES["STAGE-COMMON-1"].told.value, text)
        self.assertIn("## The build file", markdown(brief("build")))      # the frame around the rules
        self.assertNotIn("## Task mode", markdown(brief("plan")))         # a section whose rules all hold for another kind
        self.assertIn("## Task mode", markdown(brief("plan", StoryKind.TASK)))
        self.assertEqual(brief_model(first)["told"][0]["rule"], first.told[0].rule.value)



class FrameTest(unittest.TestCase):
    """The frames and the told rules give back what the skills say, word for word — while the skills are still read,
    neither may drift from the other."""

    def test_each_skill_is_its_stages_frame_with_its_rules_in_place(self):
        told = {r.id: r for r in RULES.values() if r.part is RulePart.TOLD and r.told is not None}
        placed = set(told)
        texts = [(f"stage-{s.name.value}/SKILL.md", s.frame) for s in workflow().stages if s.frame is not None]
        texts.append(("factory-run/reference/stage-common.md", workflow().every_stage))
        self.assertEqual(8, len(texts))
        for skill, frame in texts:
            with open(os.path.join(SKILLS, skill), encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            if lines[0] == "---":
                lines = lines[lines.index("---", 1) + 1:]
            body = "\n".join(lines).strip("\n").split("\n", 1)[1].strip("\n")      # without the title
            self.assertEqual(body, expanded(frame, told, placed)[0].value, skill)


if __name__ == "__main__":
    unittest.main()