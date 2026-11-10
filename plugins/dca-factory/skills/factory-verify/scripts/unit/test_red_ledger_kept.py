"""The test gate's red record keeps a test this run could not judge: a run that broke on something else — the
tests did not compile, no report shows the test — says nothing about whether the test was red."""

import unittest

from dca_factory.delivery.application.delivery.check_stage import Verdict
from dca_factory.delivery.application.delivery.process_checks import test_state
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.model.story_words import Count, Place, ScenarioKey, Selector
from dca_factory.delivery.domain.model.suite_run import (CommandKey, Evidence, RedLedger, RunEnd, RunState, TestOutcome,
                                                         TestRun)

UNIT, BROWSER = "a.WidgetTest#counts", "a.WidgetBrowserTest#shows"


def outcome(selector, state):
    return TestOutcome(ScenarioKey("k"), Selector(selector), Place("src/" + selector.split("#")[0] + ".java"),
                       CommandKey("test"), state, Evidence.REPORT, Detail(""), Detail("run"), None, Count(1),
                       Detail(""), Count(0), False)


class Runs:
    """The stage's runs: one test run with the outcomes given, and the red record before it."""

    def __init__(self, states, earlier):
        self.states, self.earlier, self.written = states, earlier, None

    def tests(self, mapping, located, whole_for):
        items = tuple(outcome(s, state) for s, state in self.states.items()) + (RunEnd(Detail("run"), True),)
        return TestRun(True, items), {}

    def ledger(self, story, red, located):
        return RedLedger(True, Detail(".tests-red"), frozenset(Selector(s) for s in self.earlier), (), True,
                         frozenset())

    def digests(self, story):
        return dict(self.earlier)

    def write_ledger(self, story, selectors, located, kept):
        self.written = (set(selectors), dict(kept))


class RedLedgerKept(unittest.TestCase):

    def run_red(self, states, earlier):
        runs = Runs(states, earlier)
        test_state(Verdict(), runs, {"test": "x"}, {"k": list(states)}, "red", {s: "f" for s in states}, "S-1")
        return runs.written

    def test_a_test_no_report_shows_keeps_its_earlier_entry(self):
        red, kept = self.run_red({UNIT: RunState.FAILED, BROWSER: RunState.NOT_REPORTED},
                                 {UNIT: "u1", BROWSER: "b1"})
        self.assertEqual(red, {UNIT})
        self.assertEqual(kept, {BROWSER: "b1"})

    def test_a_skipped_test_keeps_its_earlier_entry(self):
        _red, kept = self.run_red({BROWSER: RunState.SKIPPED}, {BROWSER: "b1"})
        self.assertEqual(kept, {BROWSER: "b1"})

    def test_a_test_never_seen_red_gains_no_entry_by_not_running(self):
        red, kept = self.run_red({UNIT: RunState.FAILED, BROWSER: RunState.NOT_REPORTED}, {})
        self.assertEqual((red, kept), ({UNIT}, {}))

    def test_a_test_that_ran_red_is_recorded_anew(self):
        red, kept = self.run_red({BROWSER: RunState.FAILED}, {BROWSER: "b1"})
        self.assertEqual((red, kept), ({BROWSER}, {}))


if __name__ == "__main__":
    unittest.main()
