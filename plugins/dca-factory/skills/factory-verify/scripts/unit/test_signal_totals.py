"""The quality figures summed over stories: why a story carries no rule verdict, and findings under a perspective the
profile does not know (WP-176)."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.status.texts import signal_totals


def row(done=True, rules=None, tested=True, findings=None):
    return dict(done=done, signals=dict(rules=rules, tested=tested, findings=findings))


class SignalTotalsTest(unittest.TestCase):

    def test_a_story_without_a_verdict_says_why(self):
        total = signal_totals([row(rules={"killed": 2}), row(rules={}), row(rules=None, tested=True),
                               row(rules=None, tested=False), row(done=False, rules=None, tested=False)])
        self.assertEqual((2, 1, 1, 1, 2), (total["measured"], total["not_measured"], total["without_test"],
                                           total["open"], total["named"]))
        self.assertEqual(1.0, total["kill_rate"])

    def test_a_finding_under_a_perspective_the_profile_does_not_know_counts_as_other(self):
        total = signal_totals([row(findings={"ddd": 2, "plan": 1, "clean-code / ddd": 1})], {"ddd", "clean-code"})
        self.assertEqual({"ddd": 2, "other": 2}, total["findings"])
        self.assertEqual({"ddd": 2, "plan": 1, "clean-code / ddd": 1},
                         signal_totals([row(findings={"ddd": 2, "plan": 1, "clean-code / ddd": 1})])["findings"])



class CreatingActionTest(unittest.TestCase):
    """A press that has an agent write something new says so; one that runs or records what a person decided does
    not."""

    def test_an_action_says_whether_an_agent_writes_something_new(self):
        from dca_factory.delivery.application.status.actions import make_action
        names = lambda word: word == "s-1"
        self.assertTrue(make_action(names, skill="/factory-backlog stories account", label="suggest stories")["creates"])
        self.assertTrue(make_action(names, skill="/factory-run show the newest first", label="wish")["creates"])
        self.assertFalse(make_action(names, skill="/factory-run s-1", label="run now")["creates"])
        self.assertNotIn("creates", make_action(names, shell="bash factory.sh setup", label="set up"))


class LaneTest(unittest.TestCase):
    """A story's lane on the backlog follows its state as the schedule reads it, never the words a view shows."""

    def test_a_draft_stays_a_draft_whatever_waits_on_it(self):
        from dca_factory.delivery.application.status.show_status import LANES
        lane = lambda state: LANES.get(state, "approved")
        self.assertEqual(["draft", "approved", "approved", "running", "running", "delivered", "superseded"],
                         [lane(s) for s in ("unreleased", "ready", "blocked", "resumable", "waiting", "delivered",
                                            "superseded")])

if __name__ == "__main__":
    unittest.main()
