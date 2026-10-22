"""WP-148 B/C: the raw facts of one story the bench aggregates — questions and assumptions counted, each named rule's
verdict at the test gate, acceptance corrections by reason code. Counted, never rated."""

import os
import tempfile
import unittest

from support import contract, write
from dca_factory import gate

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
        write(os.path.join(self.runs, "S-1", "plan.md"), PLAN)
        records = [record("question", "applied", "b"), record("question", "open"),
                   record("acceptance", "answered", "accepted")]
        signals = gate.story_signals(self.runs, "S-1", records, BODY)
        self.assertEqual((signals["asked"], signals["answered"]), (2, 1))
        self.assertEqual((signals["assumptions_open"], signals["assumptions_answered"], signals["plan_open"]), (1, 2, 1))
        self.assertEqual(signals["corrections"], {})

    def test_each_rules_verdict_is_counted_from_the_gates_record(self):
        write(os.path.join(contract.evidence_dir(self.runs, "S-1"), gate.INVARIANT_BREAKS),
              "Title\t1\tx.TitleTest#a\tred\nTitle\t2,3\tx.TitleTest#b\tkilled\nDue\t1\tx.DueTest#c\tsurvived\n")
        self.assertEqual(gate.story_signals(self.runs, "S-1", [], "")["rules"], {"red": 1, "killed": 2, "survived": 1})

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


if __name__ == "__main__":
    unittest.main()
