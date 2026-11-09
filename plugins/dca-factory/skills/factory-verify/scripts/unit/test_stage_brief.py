"""A stage's brief: what it is told for one story, decided over the workflow and the rules."""

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
from dca_factory.delivery.domain.model.brief_facts import BriefFacts
from dca_factory.delivery.domain.model.story_words import Place
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.service.stage_brief import Carrier, CarrierRole, MARKER, StageBrief, written



def brief(stage, kind=StoryKind.STORY, carriers=()):
    return StageBrief(workflow()).of(StageName(stage), kind, list(RULES.values()),
                                     [RuleId(r) for r in judging(stage, kind)], carriers)


class StageBriefTest(unittest.TestCase):

    def test_a_stage_is_told_what_every_stage_is_told_first_then_its_own(self):
        told = [t.rule.value for t in brief("build").told]
        own = [r for r in told if r.startswith("STAGE-BUILD-")]
        self.assertTrue(told[0].startswith("STAGE-COMMON-"), told[:3])
        self.assertLess(told.index("STAGE-COMMON-1"), told.index(own[0]))
        # a told rule of every stage no frame places closes what every stage is told
        self.assertLess(max(told.index(r) for r in told if r.startswith("STAGE-FILES-")), told.index(own[0]))
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

    def test_what_every_stage_is_told_is_the_same_for_each_stage_and_apart_from_its_own(self):
        plan, build = brief("plan"), brief("build")
        self.assertEqual(plan.common, build.common)
        self.assertIn(RULES["STAGE-COMMON-1"].told.value, plan.common.value)
        self.assertIn(RULES["STAGE-FILES-9"].told.value, plan.common.value)
        self.assertNotIn(RULES["STAGE-COMMON-1"].told.value, build.own.value)
        self.assertIn("## The build file", build.own.value)
        self.assertEqual(f"{build.common.value}\n\n{build.own.value}", build.said.value)
        # the text a stage reads without what every stage is told points to where that stands
        alone = written(build, build.own, Place("brief/every-stage.md")).value
        self.assertIn("`brief/every-stage.md`", alone)
        self.assertNotIn(RULES["STAGE-COMMON-1"].told.value, alone)



class BriefedTest(unittest.TestCase):
    """GATE-BRIEF: which hand-overs the gate after a stage holds to their brief, and what it says of one."""

    def test_a_gate_after_its_stage_holds_its_hand_over_and_those_no_gate_after_them_checks(self):
        def at(stage, kind=StoryKind.STORY):
            return [s.name.value for s in workflow().briefed_at(StageName(stage), kind)]
        self.assertEqual(["plan", "test"], at("test"))
        self.assertEqual(["build"], at("build"))
        self.assertEqual(["judge", "document"], at("document"))
        self.assertEqual(["plan", "build"], at("build", StoryKind.TASK))     # a task has no test stage
        self.assertEqual([], at("plan"))                                     # its gate runs before it
        self.assertEqual([], at("judge"))

    def test_a_hand_over_that_names_another_brief_or_none_is_refused(self):
        def said(given, named):
            facts = BriefFacts(Place("runs/S/build.md"), Detail(given) if given else None,
                               Detail(named) if named else None)
            return [(f.state.value, f.said.value) for f in facts.findings()]
        self.assertEqual([], said(None, None))                      # a stage run by hand was given none
        self.assertEqual("fail", said("abc", None)[0][0])
        self.assertIn("`brief: abc`", said("abc", None)[0][1])
        self.assertEqual("fail", said("abc", "def")[0][0])
        self.assertEqual("pass", said("abc", "abc")[0][0])


class FrameTest(unittest.TestCase):
    """The frames place the told rules: every marker names a rule file, and every told rule stands where a frame places
    it — or, placed by none, says where the rest of it stands."""

    def test_every_marker_names_a_told_rule_and_every_told_rule_is_placed(self):
        told = {r.id: r for r in RULES.values() if r.part is RulePart.TOLD and r.retired is None}
        frames = [s.frame for s in workflow().stages if s.frame is not None] + [workflow().every_stage]
        marked = [RuleId(m.group(1)) for frame in frames for line in frame.value.splitlines()
                  for m in [MARKER.match(line)] if m]
        self.assertEqual([], [r.value for r in marked if r not in told])
        self.assertEqual(len(marked), len(set(marked)))                     # each placed once
        self.assertEqual([], sorted(r.value for r in told if r not in marked and told[r].see is None))


if __name__ == "__main__":
    unittest.main()