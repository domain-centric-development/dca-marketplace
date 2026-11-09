"""A break's verdict from its run (WP-68, WP-107): red under the break passes, also when it was red on a timeout —
the note travels with it; green fails; a run that shows nothing is unchecked, and the reason leads the message."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.verdict import CheckName, Finding, FindingState, Said
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.service.break_checks import BreakOutcome, BreakResult, RuleProof


def seen(*entries):
    return tuple(Finding(FindingState(state), CheckName("tests-red"), Said(said)) for state, said in entries)


class BreakVerdictTest(unittest.TestCase):

    def test_red_is_red(self):
        verdict = BreakResult.of(seen(("pass", "X#y is red (k)")))
        self.assertEqual((BreakOutcome.RED, ""), (verdict.outcome, verdict.said.value))

    def test_red_on_a_timeout_is_red_with_the_note(self):
        verdict = BreakResult.of(seen(("pass", "X#y is red (k)"), ("note", "X#y is red on a timeout")))
        self.assertIs(BreakOutcome.RED, verdict.outcome)
        self.assertIn("timeout", verdict.said.value)

    def test_green_under_the_break_is_green(self):
        self.assertIs(BreakOutcome.GREEN, BreakResult.of(seen(("fail", "X#y passes before the build stage"))).outcome)

    def test_nothing_shown_is_unchecked_and_says_why_first(self):
        verdict = BreakResult.of(seen(("fail", "X#y: no test report from this run shows it ran")))
        self.assertIs(BreakOutcome.UNCHECKED, verdict.outcome)
        self.assertTrue(verdict.said.value.startswith("X#y: no test report"))


class RuleProofTest(unittest.TestCase):
    """A rule's test green now that an earlier run of the gate saw red, in this version of its file, keeps that proof
    (WP-186, 0.144.1); without it, a green test still needs its break."""

    GREEN = BreakResult(BreakOutcome.GREEN, Detail(""))

    def test_green_now_and_seen_red_before_is_red(self):
        self.assertIs(RuleProof.RED, RuleProof.seen_red_before(self.GREEN))

    def test_green_now_and_never_seen_red_needs_its_break(self):
        self.assertIs(RuleProof.NO_BREAK, RuleProof.of(self.GREEN, None))
        self.assertIs(RuleProof.KILLED, RuleProof.of(self.GREEN, BreakResult(BreakOutcome.RED, Detail(""))))


if __name__ == "__main__":
    unittest.main()
