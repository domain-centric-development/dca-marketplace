"""Every verdict in the journal and what became of the findings of the one before (WP-209)."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.journal_files import journal_events
from dca_factory.delivery.adapter.outgoing.files.judge_record import record_verdict
from dca_factory.delivery.application.status.texts import signal_totals
from dca_factory.delivery.domain.model.judge_rows import Closure, FindingOutcome, NextSeen, outcome_of

DIFF = ("diff --git a/src/Thing.java b/src/Thing.java\n--- a/src/Thing.java\n+++ b/src/Thing.java\n"
        "@@ -1,2 +1,3 @@\n class Thing {\n+  int {name};\n }\n")


def judge(verdict, rows):
    return (f"## Verdict\nverdict: {verdict}\n\n## Confirmed defects\n| Perspective | File:line | Severity | Defect | Fix |\n"
            "|---|---|---|---|---|\n" + "".join(f"| ddd | src/Thing.java:{line} | {severity} | unchecked null | f |\n"
                                               for line, severity in rows))


class Runs:
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.dir.name, ".dca-factory", "runs")
        os.makedirs(os.path.join(self.runs, "S-1"))
        os.makedirs(os.path.join(self.dir.name, ".dca-factory", "evidence", "S-1"))

    def write(self, verdict, rows, name="a"):
        with open(os.path.join(self.runs, "S-1", "judge.md"), "w") as handle:
            handle.write(judge(verdict, rows))
        with open(os.path.join(self.dir.name, ".dca-factory", "evidence", "S-1", "story.diff"), "w") as handle:
            handle.write(DIFF.replace("{name}", name))

    def outcomes(self):
        return [e["fields"]["outcome"] for e in journal_events(self.runs, "S-1") if e["kind"] == "outcome"]


class OutcomeTest(unittest.TestCase):

    def test_the_rule(self):
        self.assertIs(FindingOutcome.OVERRULED, outcome_of(NextSeen.RAISED_AGAIN, Closure.ANSWERED))
        self.assertIs(FindingOutcome.REPEATED, outcome_of(NextSeen.RAISED_AGAIN, Closure.OPEN))
        self.assertIs(FindingOutcome.FIXED, outcome_of(NextSeen.GONE_LINE_CHANGED, Closure.OPEN))
        self.assertIs(FindingOutcome.DROPPED, outcome_of(NextSeen.GONE_LINE_SAME, Closure.OPEN))

    def test_gone_with_its_line_changed_is_fixed(self):
        runs = Runs()
        runs.write("changes-requested", [(2, "major")], "a")
        record_verdict(runs.runs, "S-1")
        runs.write("pass", [], "b")
        record_verdict(runs.runs, "S-1")
        self.assertEqual(["fixed"], runs.outcomes())

    def test_gone_with_its_line_as_it_was_is_dropped(self):
        runs = Runs()
        runs.write("changes-requested", [(2, "major")], "a")
        record_verdict(runs.runs, "S-1")
        runs.write("pass", [(9, "minor")], "a")
        record_verdict(runs.runs, "S-1")
        self.assertEqual(["dropped"], runs.outcomes())

    def test_raised_again_repeats_and_an_answer_overrules(self):
        runs = Runs()
        runs.write("changes-requested", [(2, "major")])
        record_verdict(runs.runs, "S-1")
        runs.write("changes-requested", [(2, "blocker")])
        record_verdict(runs.runs, "S-1", frozenset({"src/Thing.java:2"}))
        self.assertEqual(["overruled"], runs.outcomes())

    def test_the_same_verdict_is_journaled_once(self):
        runs = Runs()
        runs.write("changes-requested", [(2, "major")])
        record_verdict(runs.runs, "S-1")
        record_verdict(runs.runs, "S-1")
        self.assertEqual(1, sum(1 for e in journal_events(runs.runs, "S-1") if e["kind"] == "signal"))


class TotalsTest(unittest.TestCase):

    def test_first_pass_rounds_and_false_alarms(self):
        rows = [dict(done=True, signals=dict(judged=1, first_pass=True, judge_rounds=0, outcomes={})),
                dict(done=True, signals=dict(judged=2, first_pass=False, judge_rounds=1,
                                             outcomes={"fixed": 1, "dropped": 1}, outcome_by={"ddd": {"fixed": 1, "dropped": 1}}))]
        total = signal_totals(rows)
        self.assertEqual((1, 2, 0.5, 0.5), (total["first_pass"], total["judged_stories"], total["rounds_per_story"],
                                             total["false_alarm_share"]))
        self.assertIn("1/2 pass first time", total["line"])


if __name__ == "__main__":
    unittest.main()
