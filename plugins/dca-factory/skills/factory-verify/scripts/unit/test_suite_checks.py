"""Which red tests of a whole suite run are run again alone (WP-113)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.stage_story import Count, Presence
from dca_factory.delivery.domain.service.suite_checks import FLAKY_LIMIT, SuiteChecks


class Retries(unittest.TestCase):

    def test_a_few_red_tests_outside_the_story_run_again(self):
        self.assertIs(SuiteChecks.retries(Count(1), Presence.ABSENT), Presence.PRESENT)
        self.assertIs(SuiteChecks.retries(FLAKY_LIMIT, Presence.ABSENT), Presence.PRESENT)

    def test_none_too_many_or_one_of_the_storys_own_run_no_more(self):
        self.assertIs(SuiteChecks.retries(Count(0), Presence.ABSENT), Presence.ABSENT)
        self.assertIs(SuiteChecks.retries(Count(FLAKY_LIMIT.value + 1), Presence.ABSENT), Presence.ABSENT)
        self.assertIs(SuiteChecks.retries(Count(1), Presence.PRESENT), Presence.ABSENT)


if __name__ == "__main__":
    unittest.main()
