"""A break's verdict from its run (WP-68, WP-107): red under the break passes, also when it was red on a timeout —
the note travels with it; green fails; a run that shows nothing is unchecked, and the reason leads the message."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory import gate


class BreakVerdictTest(unittest.TestCase):

    def test_red_is_red(self):
        self.assertEqual(("red", ""), gate.break_verdict([("pass", "X#y is red (k)")]))

    def test_red_on_a_timeout_is_red_with_the_note(self):
        verdict, said = gate.break_verdict([("pass", "X#y is red (k)"), ("note", "X#y is red on a timeout")])
        self.assertEqual("red", verdict)
        self.assertIn("timeout", said)

    def test_green_under_the_break_is_green(self):
        self.assertEqual("green", gate.break_verdict([("fail", "X#y passes before the build stage")])[0])

    def test_nothing_shown_is_unchecked_and_says_why_first(self):
        verdict, said = gate.break_verdict([("fail", "X#y: no test report from this run shows it ran")])
        self.assertEqual("unchecked", verdict)
        self.assertTrue(said.startswith("X#y: no test report"))


if __name__ == "__main__":
    unittest.main()
