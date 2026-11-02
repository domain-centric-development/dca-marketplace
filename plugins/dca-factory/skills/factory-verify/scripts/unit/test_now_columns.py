"""The start page's four columns: each its count, its line, the one item and the one action, every number once
(WP-179)."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.status.now_columns import now_columns, places_of

RUN = dict(text="", skill="/factory-run a", label="run it", request=dict(kind="run"))


def row(story, done=False, delivered=""):
    return dict(story=story, title=story.upper(), done=done, delivered=delivered)


class NowColumnsTest(unittest.TestCase):

    def columns(self, running=(), waiting=(), journeys=(), backlog_on=False):
        rows = [row("a"), row("b"), row("c", True, "2026-11-02T10:00:00Z"), row("d", True, "2026-11-01T10:00:00Z")]
        return {c["column"]: c for c in now_columns(rows, dict(ready=["a", "b"], blocked=3), "a",
                                                    dict(text="a can start", action=RUN), list(running),
                                                    list(waiting), list(journeys), backlog_on, 2, ["c", "d"])}

    def test_the_cycle_in_order_each_column_says_its_count_once(self):
        cols = self.columns()
        self.assertEqual(["backlog", "run", "decide", "delivered"], list(cols))
        self.assertEqual((2, "released — 3 more blocked", "A", RUN), (cols["backlog"]["count"], cols["backlog"]["line"],
                                                                      cols["backlog"]["title"], cols["backlog"]["action"]))
        self.assertEqual((2, 4, "50 %", "2026-11-02T10:00:00Z"), (cols["delivered"]["count"], cols["delivered"]["total"],
                                                                  cols["delivered"]["line"], cols["delivered"]["last"]))

    def test_nothing_running_offers_the_backlog_and_a_running_backlog_does_not(self):
        self.assertEqual("up", self.columns()["run"]["action"]["call"])
        self.assertEqual(("of 2 places", "the backlog is off"), (self.columns()["run"]["line"], self.columns()["run"]["sub"]))
        self.assertIsNone(self.columns(backlog_on=True)["run"]["action"])
        self.assertEqual("B", self.columns(running=[dict(story="b", stage="build")])["run"]["title"])

    def test_decide_names_its_first_question_and_is_marked_while_one_waits(self):
        ask = dict(story="a", what="draft — waits for your release", action=dict(label="release", request=dict()))
        decide = self.columns(waiting=[ask, dict(ask, place="discover")])["decide"]
        self.assertEqual((1, True, "A"), (decide["count"], decide["hot"], decide["title"]))
        self.assertFalse(self.columns()["decide"]["hot"])

    def test_delivered_names_one_unguarded_epic_and_counts_the_others(self):
        guards = [dict(epic=e, action=dict(label="add guard")) for e in ("x", "y", "z")]
        col = self.columns(journeys=guards)["delivered"]
        self.assertEqual(("x is unguarded", "2 more epics without a journey test"), (col["title"], col["sub"]))

    def test_places_from_the_profile(self):
        self.assertEqual((1, 3, 1), (places_of({}), places_of({"parallel": "3"}), places_of({"parallel": "zero"})))


if __name__ == "__main__":
    unittest.main()
