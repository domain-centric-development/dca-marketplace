"""Acceptance figures from the files the factory already writes: how long an acceptance waited, how it came out, and
the rework — a story's production files another story changed again within fourteen days."""

import datetime
import os
import tempfile
import unittest

from support import write
from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from dca_factory.delivery.adapter.incoming.cli.cli_command import acceptance_rows
from dca_factory.delivery.adapter.outgoing.files import status_facts
from dca_factory.delivery.application.status.texts import signal_totals, took_text, with_rework


def acceptance(asked, at=None, answer="accepted"):
    front = {"id": "S-1-accept-1", "kind": "acceptance", "asked": asked}
    return ("path", front, "# Accept", "answered" if at else "open", {"answer": answer, "at": at} if at else {})


def moment(day):
    return datetime.datetime(2026, 11, day, tzinfo=datetime.timezone.utc)


class AcceptanceTest(unittest.TestCase):

    def test_a_story_nobody_was_asked_to_accept_has_no_figures(self):
        self.assertIsNone(status_facts.acceptance_figures([]))

    def test_the_wait_the_outcome_and_the_corrections(self):
        records = [acceptance("2026-11-01T10:00:00Z", "2026-11-01T12:00:00Z", "correction: two cards on m"),
                   acceptance("2026-11-02T10:00:00Z", "2026-11-02T10:30:00Z")]
        self.assertEqual(status_facts.acceptance_figures(records),
                         dict(waited=2 * 3600 + 1800, outcome="accepted", corrections=1))

    def test_one_still_open_says_so(self):
        self.assertEqual(status_facts.acceptance_figures([acceptance("2026-11-01T10:00:00Z")]),
                         dict(waited=None, outcome="open", corrections=0))


class ReworkTest(unittest.TestCase):

    def test_the_production_files_a_story_changed_tests_and_the_rest_left_out(self):
        with tempfile.TemporaryDirectory() as root:
            runs = os.path.join(root, ".dca-factory", "runs")
            write(os.path.join(evidence_dir(runs, "S-1"), "changed.txt"),
                  "modified\tsrc/main/java/a/Thing.java\nadded\tsrc/test/java/a/ThingTest.java\n"
                  "modified\tREADME.md\nadded\tapp/thing_test.py\nmodified\tapp/thing.py\n")
            self.assertEqual(status_facts.changed_production(runs, "S-1"), ["src/main/java/a/Thing.java", "app/thing.py"])

    def test_another_story_delivered_within_fourteen_days_that_changed_a_file_again_is_rework(self):
        rows = [dict(story="S-1", epic="e", delivered=moment(1), signals=dict(production=["a.py", "b.py"])),
                dict(story="S-2", epic="e", delivered=moment(5), signals=dict(production=["a.py"])),
                dict(story="S-3", epic="e", delivered=moment(20), signals=dict(production=["b.py"]))]
        with_rework(rows)
        self.assertEqual([r["signals"].get("rework") for r in rows], [1, 0, 0])
        self.assertEqual(signal_totals(rows)["rework"], 1)

    def test_test_strength_summed_measured_skipped_and_absent_apart(self):
        rows = [dict(story="S-1", signals=dict(mutation="82")), dict(story="S-2", signals=dict(mutation="72.73")),
                dict(story="S-3", signals=dict(mutation="60")), dict(story="S-4", signals=dict(mutation="skipped")),
                dict(story="S-5", signals=dict(mutation="no score")), dict(story="S-6", signals={})]
        totals = signal_totals(rows)
        self.assertEqual((totals["mutation_measured"], totals["mutation_skipped"], totals["mutation_median"]),
                         (3, 2, 72.7))
        self.assertIn("mutation median 72.7 % (3 measured)", totals["line"])

    def test_no_measure_is_no_median_never_zero(self):
        totals = signal_totals([dict(story="S-1", signals=dict(mutation="skipped")), dict(story="S-2", signals={})])
        self.assertEqual((totals["mutation_measured"], totals["mutation_skipped"], totals["mutation_median"]),
                         (0, 1, None))
        self.assertNotIn("mutation", totals["line"])

    def test_the_usage_view_lists_per_epic_the_stories_with_figures(self):
        model = dict(epics=[dict(epic="e", rows=[
            dict(story="S-1", signals=dict(acceptance=dict(waited=3600, outcome="accepted", corrections=0), rework=2)),
            dict(story="S-2", signals={})])])
        self.assertEqual(acceptance_rows(model),
                         [["e", "", "", "", ""], ["  ↳ S-1", took_text(3600), "accepted", "0", "2"]])


if __name__ == "__main__":
    unittest.main()
