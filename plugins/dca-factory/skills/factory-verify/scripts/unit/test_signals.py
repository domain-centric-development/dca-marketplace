"""WP-148 B/C: the raw facts of one story the bench aggregates — questions and assumptions counted, each named rule's
verdict at the test gate, acceptance corrections by reason code. Counted, never rated."""

import os
import tempfile
import unittest

from support import write
from dca_factory import gate, state
from dca_factory.delivery.adapter.outgoing.files import journal_files as journal

BODY = """# A story

## Assumptions
- open: is an archived task shown?
- answered: a title is at most 200 characters (S-1-01)
- answered: trimmed before the check (S-1-02)
"""

PLAN = """# Plan

## Open assumptions
- the sort order of equal titles
- none
"""


def record(kind, state, answer=""):
    front = {"id": f"S-1-{kind}", "kind": kind}
    return ("path", front, "# question", state, {"answer": answer} if answer else {})


class Signals(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.scratch.name, ".dca-factory", "runs")

    def tearDown(self):
        self.scratch.cleanup()

    def test_questions_assumptions_and_what_the_plan_left_open_are_counted(self):
        records = [record("question", "applied", "b"), record("question", "open"),
                   record("acceptance", "answered", "accepted")]
        self.assertIsNone(gate.story_signals(self.runs, "S-1", records, BODY)["plan_open"])
        state.journal_signal(self.runs, "S-1", "plan", open=len(gate.plan_left_open(PLAN)))
        signals = gate.story_signals(self.runs, "S-1", records, BODY)
        self.assertEqual((signals["asked"], signals["answered"]), (2, 1))
        self.assertEqual((signals["assumptions_open"], signals["assumptions_answered"], signals["plan_open"]), (1, 2, 1))
        self.assertEqual(signals["corrections"], {})

    def test_each_rules_verdict_is_counted_from_the_last_group_the_test_gate_wrote(self):
        self.assertIsNone(gate.story_signals(self.runs, "S-1", [], "")["rules"])
        state.journal_signal(self.runs, "S-1", "rules", [("rule", "x.TitleTest#a", dict(element="Title", rules="1", verdict="unchecked"))])
        state.journal_signal(self.runs, "S-1", "rules", [
            ("rule", "x.TitleTest#a", dict(element="Title", rules="1", verdict="red")),
            ("rule", "x.TitleTest#b", dict(element="Title", rules="2,3", verdict="killed")),
            ("rule", "x.DueTest#c", dict(element="Due", rules="1", verdict="survived"))])
        self.assertEqual(gate.story_signals(self.runs, "S-1", [], "")["rules"], {"red": 1, "killed": 2, "survived": 1})

    def test_the_judges_findings_by_perspective_and_domain_code_once_per_judge_file(self):
        self.assertIsNone(gate.story_signals(self.runs, "S-1", [], "")["findings"])
        judge = ("## Verdict\nverdict: pass\n\n## Confirmed defects\n"
                 "| Perspective | File:line | Severity | In plain words | Defect | Fix |\n|---|---|---|---|---|---|\n"
                 "| ddd | A.java:3 | minor | a | domain-term: `Item` is a `Line` | rename |\n"
                 "| clean-code | B.java:9 | minor | b | a long method | split |\n")
        gate.record_judge_signal(self.runs, "S-1", judge)
        gate.record_judge_signal(self.runs, "S-1", judge)
        signals = gate.story_signals(self.runs, "S-1", [], "")
        self.assertEqual((signals["findings"], signals["domain"]), ({"ddd": 1, "clean-code": 1}, {"domain-term": 1}))
        self.assertEqual(sum(1 for e in journal.journal_events(self.runs, "S-1") if e["kind"] == "signal"), 1)

    def test_corrections_are_counted_by_their_reason_code(self):
        records = [record("acceptance", "applied", "correction: domain-invariant: a done task keeps its subtasks"),
                   record("acceptance", "applied", "correction: the button is too small"),
                   record("acceptance", "answered", "correction: nonsense: words"),
                   record("acceptance", "answered", "accepted")]
        self.assertEqual(gate.story_signals(self.runs, "S-1", records, "")["corrections"],
                         {"domain-invariant": 1, "uncoded": 2})

    def test_the_reason_code_of_an_answer(self):
        self.assertEqual(gate.correction_code("correction: assumption: the code chose the order"), "assumption")
        self.assertEqual(gate.correction_code("Correction: Behavioural: it should sum"), "behavioural")
        self.assertEqual(gate.correction_code("correction: plain words"), "uncoded")
        self.assertIsNone(gate.correction_code("accepted"))


class Totals(unittest.TestCase):
    """WP-150 E: the figures over many stories — the factory computes them, every view and the bench print them."""

    def test_rates_from_the_measured_stories_and_a_story_before_the_rules_is_not_measured_not_zero(self):
        from dca_factory.delivery.application.status import texts
        rows = [dict(signals=dict(rules={"red": 3, "killed": 1}, asked=2, answered=1, domain={"domain-concept": 2},
                                  corrections={"domain-term": 1}, findings={"ddd": 2})),
                dict(signals=dict(rules={"survived": 1}, domain={"domain-term": 1})),
                dict(signals=dict(rules=None, asked=1, answered=1))]
        totals = texts.signal_totals(rows)
        self.assertEqual((totals["measured"], totals["not_measured"], totals["named"]), (2, 1, 5))
        self.assertEqual((totals["kill_rate"], totals["guarded_rate"]), (0.2, 0.8))
        self.assertEqual((totals["asked"], totals["answered"], totals["domain"]), (3, 2, {"domain-concept": 2, "domain-term": 1}))
        self.assertEqual(texts.signals_line(totals), "kill rate 0.20 · guarded 0.80 (5 rules named) · domain findings "
                                                   "2 concept · 1 term · corrections 1 term")
        nothing = texts.signal_totals([dict(signals=dict(rules=None))])
        self.assertIsNone(nothing["kill_rate"])
        self.assertEqual(texts.signals_line(nothing), "rules not measured")


if __name__ == "__main__":
    unittest.main()
