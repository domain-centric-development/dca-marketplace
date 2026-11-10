"""The kind of question a stage asks: one word from the factory's list, the same list the stages are told."""

import os
import re
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.domain.model.question_tag import QuestionTag
from dca_factory.delivery.domain.model.story_words import Detail

RULE = os.path.join(support.SCRIPTS, "workflow", "rules", "stage", "STAGE-COMMON-30B.md")


class QuestionTagTest(unittest.TestCase):

    def test_a_tag_is_read_in_any_case_and_a_word_outside_the_list_is_none(self):
        self.assertIs(QuestionTag.TEST_LEVEL, QuestionTag.written(Detail(" `Test-Level` ")))
        self.assertIsNone(QuestionTag.written(Detail("layout")))
        self.assertIsNone(QuestionTag.written(Detail("")))

    def test_the_stages_are_told_exactly_the_list_the_gate_checks(self):
        with open(RULE, encoding="utf-8") as handle:
            told = handle.read()
        listed = re.search(r"one word from this list: (.*?)\. The gate", told, re.S).group(1)
        self.assertEqual([t.value for t in QuestionTag], re.findall(r"`([a-z-]+)`", listed))
