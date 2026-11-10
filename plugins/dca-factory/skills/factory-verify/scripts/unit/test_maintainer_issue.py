"""What goes up to the maintainers names none of the project (WP-185, point 4): only the pipeline's own words."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.domain.model.lesson import LessonKind, LessonPlace, SignalKey
from dca_factory.delivery.domain.model.maintainer_issue import IssueTarget, MaintainerIssue
from dca_factory.delivery.domain.model.story_words import Count, Detail


def issue(kind, key, place=LessonPlace.FACTORY):
    return MaintainerIssue(IssueTarget(place), kind, SignalKey(key), Count(4), Detail("dca-factory 9.9.9, contract 99"))


class MaintainerIssueTest(unittest.TestCase):

    def test_a_question_says_its_tag_and_never_its_context(self):
        text = issue(LessonKind.QUESTION, "lending/test-level").text().value
        self.assertIn("question tag: `test-level`", text)
        self.assertNotIn("lending", text)
        self.assertIn("target: factory", text)
        self.assertIn("stories: 4", text)

    def test_a_finding_names_a_rule_of_the_method_but_neither_a_project_rule_nor_a_project_perspective(self):
        method = issue(LessonKind.FINDING, "hexagonal/dca-hex-014", LessonPlace.RULE_LIBRARY).text().value
        self.assertIn("rule: `DCA-HEX-014`", method)
        own = issue(LessonKind.FINDING, "billing-review/acme-pay-3", LessonPlace.RULE_LIBRARY).text().value
        self.assertNotIn("acme", own.lower())
        self.assertNotIn("billing", own)
        self.assertIn("perspective: one of the project's own", own)

    def test_an_assumption_and_a_term_carry_nothing_of_their_words(self):
        for kind, key in ((LessonKind.ASSUMPTION, "loans are renewed twice → yes"), (LessonKind.TERM, "borrower")):
            with self.subTest(kind=kind):
                text = issue(kind, key, LessonPlace.KNOWLEDGE_CATALOG).text().value
                self.assertNotIn(key.split()[0], text)
                self.assertIn("nothing beyond the kind of signal and its count", text)

    def test_only_a_place_of_the_maintainers_is_a_target(self):
        with self.assertRaises(ValueError):
            IssueTarget(LessonPlace.DESCRIPTION)
