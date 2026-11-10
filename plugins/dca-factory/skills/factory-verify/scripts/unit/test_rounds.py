"""A repeated refusal gets one fresh restart, then stops: what the journal keeps of a refusal (its checks and failing
tests), when two refusals are equal, the round record the runner writes and the mark a fresh restart leaves."""

import os
import tempfile
import types
import unittest

from support import write
from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from dca_factory.delivery.adapter.outgoing.files import round_files
from dca_factory.delivery.adapter.outgoing.files.gate_journal import gate_fields
from dca_factory.delivery.application.delivery.check_stage import Verdict
from dca_factory.delivery.domain.model.refusal_history import (
    FreshRestart, GateRefusal, RefusalHistory, Repetition)
from dca_factory.delivery.domain.model.stage import StageName
from dca_factory.delivery.domain.model.story_words import Selector
from dca_factory.delivery.domain.model.verdict import CheckName

STORY = "S-1"


def refusal(stage="build", checks=("tests-green",), tests=("A#a",)):
    return GateRefusal(StageName(stage), frozenset(CheckName(c) for c in checks),
                       frozenset(Selector(t) for t in tests))


class RepetitionTest(unittest.TestCase):

    def test_one_refusal_is_new(self):
        self.assertIs(RefusalHistory((refusal(),)).repetition(), Repetition.NEW)

    def test_the_same_stage_checks_and_tests_repeat(self):
        self.assertIs(RefusalHistory((refusal(), refusal())).repetition(), Repetition.REPEATED)

    def test_another_failing_test_another_check_or_stage_is_new(self):
        for other in (refusal(tests=("B#b",)), refusal(checks=("tests-green", "suite")), refusal(stage="tidy")):
            self.assertIs(RefusalHistory((refusal(), other)).repetition(), Repetition.NEW)

    def test_a_repeat_after_the_fresh_restart_between_them(self):
        history = RefusalHistory((refusal(), refusal(), FreshRestart(StageName("build")), refusal()))
        self.assertIs(history.repetition(), Repetition.REPEATED_AFTER_FRESH)


class JournalTest(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.scratch.name, ".dca-factory", "runs")
        self.folder = evidence_dir(self.runs, STORY)

    def tearDown(self):
        self.scratch.cleanup()

    def journal(self, *lines):
        write(os.path.join(self.folder, "journal.tsv"),
              "".join(f"2026-11-10T00:00:0{n}Z\t{line}\tseq={n}\n" for n, line in enumerate(lines, 1)))

    def test_a_refused_line_names_its_failing_tests_at_most_twenty(self):
        verdict = Verdict()
        verdict.fail("tests-green", "A#a fails")
        verdict.failing_tests = [f"T#t{n}" for n in range(25)]
        fields = gate_fields(verdict, types.SimpleNamespace(record_suites=True), 1)
        tests = next(f for f in fields if f.startswith("tests="))[len("tests="):].split(",")
        self.assertEqual(len(tests), 20)
        self.assertIn("fail=tests-green", fields)
        self.assertIn("by=runner", fields)

    def test_the_history_reads_the_runners_refusals_and_fresh_restarts_since_the_rounds_were_reset(self):
        self.journal("gate\tbuild\texit=1\tfail=suite\tby=runner",
                     "rounds-reset\t-\tby=--from",
                     "gate\tbuild\texit=1\tfail=tests-green\tby=build",
                     "gate\tbuild\texit=1\tfail=tests-green\tby=runner\ttests=A#a",
                     "fresh\tbuild\trule=RUN-ROUNDS-3",
                     "gate\tbuild\texit=1\tfail=tests-green\tby=runner\ttests=A#a")
        history = round_files.refusal_history(self.runs, STORY)
        self.assertEqual(history.entries, (refusal(), FreshRestart(StageName("build")), refusal()))

    def test_the_round_record_is_a_line_a_round_written_from_the_journal_the_record_and_the_hand_over(self):
        self.journal("gate\tbuild\texit=1\tfail=tests-green\tby=runner\ttests=A#a")
        write(os.path.join(self.folder, "changed-build.txt"), "modified\tsrc/A.java\n")
        hand_over = os.path.join(self.runs, STORY, "build.md")
        write(hand_over, "brief: abc\n# Build\n\nThe page now reads the list.\n\n## Files\n- `src/A.java`\n")
        round_files.record_round(self.runs, STORY, "build", hand_over)
        round_files.record_round(self.runs, STORY, "build", hand_over)
        lines = [l for l in open(os.path.join(self.folder, "rounds.md"), encoding="utf-8").read().splitlines()
                 if l.startswith("- round ")]
        self.assertEqual(lines[0], "- round 1 · build · failed: tests-green · tests: A#a · changed: src/A.java · "
                                   "said: The page now reads the list.")
        self.assertTrue(lines[1].startswith("- round 2 · build"))

    def test_a_fresh_restart_marks_its_stage_and_sets_the_earlier_hand_over_aside(self):
        hand_over = os.path.join(self.runs, STORY, "build.md")
        write(hand_over, "# Build\n")
        round_files.mark_fresh(self.runs, STORY, "build", hand_over)
        self.assertEqual(round_files.fresh_stage(self.runs, STORY), "build")
        self.assertFalse(os.path.isfile(hand_over))
        self.assertEqual(len(os.listdir(os.path.join(self.folder, "attempts"))), 1)
        round_files.clear_fresh(self.runs, STORY)
        self.assertIsNone(round_files.fresh_stage(self.runs, STORY))


if __name__ == "__main__":
    unittest.main()
