"""Which red tests of a whole suite run are run again alone (WP-113), and when the test gate let a test through
green."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.stage_story import Count, Presence
from dca_factory.delivery.domain.model.verdict import CheckName, FindingState, Said
from dca_factory.delivery.domain.service.suite_checks import FLAKY_LIMIT, SuiteChecks
from dca_factory.delivery.domain.service.test_verdicts import RED_CHECK, TestVerdicts


class Retries(unittest.TestCase):

    def test_a_few_red_tests_outside_the_story_run_again(self):
        self.assertIs(SuiteChecks.retries(Count(1), Presence.ABSENT), Presence.PRESENT)
        self.assertIs(SuiteChecks.retries(FLAKY_LIMIT, Presence.ABSENT), Presence.PRESENT)

    def test_none_too_many_or_one_of_the_storys_own_run_no_more(self):
        self.assertIs(SuiteChecks.retries(Count(0), Presence.ABSENT), Presence.ABSENT)
        self.assertIs(SuiteChecks.retries(Count(FLAKY_LIMIT.value + 1), Presence.ABSENT), Presence.ABSENT)
        self.assertIs(SuiteChecks.retries(Count(1), Presence.PRESENT), Presence.ABSENT)


class GreenThrough(unittest.TestCase):

    def test_only_the_red_checks_pass_of_a_green_test_lets_one_through(self):
        said = Said("x.T#a is green now and was recorded red before; its expectation changed on decision S-1-01 (a)")
        self.assertIs(TestVerdicts.let_through_green(RED_CHECK, FindingState.PASS, said), Presence.PRESENT)
        self.assertIs(TestVerdicts.let_through_green(RED_CHECK, FindingState.PASS, Said("x.T#a fails")),
                      Presence.ABSENT)
        self.assertIs(TestVerdicts.let_through_green(CheckName("tests-green"), FindingState.PASS, said),
                      Presence.ABSENT)


if __name__ == "__main__":
    unittest.main()
