"""Which red tests of a whole suite run are run again alone (WP-113), and when the test gate let a test through
green."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.story_words import Count
from dca_factory.delivery.domain.model.verdict import CheckName, Finding, FindingState, RED_CHECK, Said
from dca_factory.delivery.domain.model.suite import FLAKY_LIMIT, SuiteJudged


class Retries(unittest.TestCase):

    def test_a_few_red_tests_outside_the_story_run_again(self):
        self.assertIs(SuiteJudged.retries(Count(1), Count(0)), True)
        self.assertIs(SuiteJudged.retries(FLAKY_LIMIT, Count(0)), True)

    def test_none_too_many_or_one_of_the_storys_own_run_no_more(self):
        self.assertIs(SuiteJudged.retries(Count(0), Count(0)), False)
        self.assertIs(SuiteJudged.retries(Count(FLAKY_LIMIT.value + 1), Count(0)), False)
        self.assertIs(SuiteJudged.retries(Count(1), Count(1)), False)


class GreenThrough(unittest.TestCase):

    def test_only_the_red_checks_pass_of_a_green_test_lets_one_through(self):
        said = Said("x.T#a is green now and was recorded red before; its expectation changed on decision S-1-01 (a)")
        self.assertTrue(Finding(FindingState.PASS, RED_CHECK, said).lets_through_green())
        self.assertFalse(Finding(FindingState.PASS, RED_CHECK, Said("x.T#a fails")).lets_through_green())
        self.assertFalse(Finding(FindingState.PASS, CheckName("tests-green"), said).lets_through_green())


if __name__ == "__main__":
    unittest.main()
