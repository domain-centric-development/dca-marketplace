"""The stack profile as delivery reads it (`StackProfile`) and the questions it answers (`AskProfileUseCase`)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.profile.ask_profile import AskProfileQuery, AskProfileUseCase, Question
from dca_factory.delivery.application.profile.profile_rules import stack_profile
from dca_factory.delivery.domain.model.stack_profile import Perspective, ProfileValue, SkillName, ToolName, Unit
from dca_factory.delivery.domain.model.stage import StageName

PROFILE = {
    "compile": "./gradlew testClasses", "test": "./gradlew test --rerun", "test.integration": "./gradlew it",
    "format": "{{format}}", "architecture": "make arch",
    "model.claude": "claude-opus-5-5", "model.claude.tidy": "haiku extra words",
    "carrier.build": "dca-core:dca-modelling", "review.ddd": "dca-craft:review-ddd", "knowledge": "dca-knowledge",
    "reviews": "security, ddd", "review.security": "sec-review",
}


class Profiles:
    def profile(self):
        return PROFILE


class StackProfileTest(unittest.TestCase):

    def setUp(self):
        self.profile = stack_profile(PROFILE)

    def test_a_unit_takes_its_own_tool_and_effort_then_its_heads_then_the_profiles(self):
        profile = stack_profile({"tool": "claude", "tool.review": "codex x", "tool.review.ddd": "opencode",
                                 "effort.codex": "low", "effort.codex.review": "high"})
        self.assertEqual(profile.tool_for(Unit("review:ddd")), ToolName("opencode"))
        self.assertEqual(profile.tool_for(Unit("review:clean-code")), ToolName("codex"))
        self.assertEqual(profile.tool_for(Unit("build")), ToolName("claude"))
        self.assertEqual(stack_profile({}).tool_for(Unit("build")), ToolName(""))
        self.assertEqual(profile.effort_for(ToolName("codex"), Unit("review:ddd")), ProfileValue("high"))
        self.assertEqual(profile.effort_for(ToolName("codex"), Unit("build")), ProfileValue("low"))
        self.assertEqual(profile.effort_for(ToolName("claude"), Unit("build")), ProfileValue(""))

    def test_a_tool_takes_its_stage_model_else_its_own_and_never_another_tools(self):
        self.assertEqual("haiku", self.profile.model_for(ToolName("claude"), StageName("tidy")).value)
        self.assertEqual("claude-opus-5-5", self.profile.model_for(ToolName("claude"), StageName("build")).value)
        self.assertEqual("", self.profile.model_for(ToolName("codex"), StageName("build")).value)

    def test_the_command_heads_are_the_declared_programs_once_each_without_a_placeholder(self):
        self.assertEqual(["./gradlew", "make"], [h.value for h in self.profile.command_heads()])

    def test_the_perspectives_are_the_built_ins_and_the_profiles_each_with_its_carrier(self):
        self.assertEqual((Perspective(SkillName("ddd"), SkillName("review-ddd")),
                          Perspective(SkillName("hexagonal"), SkillName("review-hexagonal")),
                          Perspective(SkillName("clean-code"), SkillName("review-clean-code")),
                          Perspective(SkillName("security"), SkillName("sec-review"))), self.profile.perspectives())

    def test_the_carriers_are_the_named_skills_without_their_plugin(self):
        self.assertEqual(["dca-knowledge", "dca-modelling", "review-ddd", "sec-review"],
                         [s.value for s in self.profile.carriers()])


class AskProfileTest(unittest.TestCase):

    def ask(self, question, **fields):
        return AskProfileUseCase(Profiles()).execute(AskProfileQuery(question, **fields))

    def test_each_question_is_answered_a_line_per_item(self):
        self.assertEqual(("make arch",), self.ask(Question.VALUE, key="architecture"))
        self.assertEqual(("",), self.ask(Question.VALUE, key="nothing"))
        self.assertEqual(("haiku",), self.ask(Question.MODEL, tool="claude", stage="tidy"))
        self.assertEqual(("./gradlew", "make"), self.ask(Question.COMMAND_HEADS))
        self.assertIn("carrier.build dca-core:dca-modelling", self.ask(Question.CARRIER_LINES))
        self.assertEqual("security\tsec-review", self.ask(Question.PERSPECTIVES)[-1])


if __name__ == "__main__":
    unittest.main()
