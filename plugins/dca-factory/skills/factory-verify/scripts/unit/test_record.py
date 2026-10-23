"""The journal is the story's record (WP-150): what a stream, a gate or a hand-over says about a story is a journal
line, written once, and the views read the journal alone — so the raw material can go."""

import os
import shutil
import time
import unittest

from support import contract, project, reports, state
from dca_factory import cli

STREAMS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "streams")
SECOND = "2026-10-10T10:00:00Z"


def window(p, name="builder.100000.out", source="claude-recorded.jsonl"):
    """A shared builder's recorded stream beside S-1's journal."""
    path = os.path.join(contract.evidence_dir(p.runs, "S-1"), name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy(os.path.join(STREAMS, source), path)
    return path


class FrozenStream(unittest.TestCase):

    def test_a_streams_parts_and_denials_are_journal_lines_once(self):
        with project() as p:
            path = window(p)
            journal = state.journal_path(p.runs, "S-1")
            self.assertTrue(state.freeze_stream(journal, path))
            self.assertFalse(state.freeze_stream(journal, path))
            events = state.journal_events(p.runs, "S-1")
            parts, _cost = reports.stream_parts(path)
            self.assertEqual([e["name"] for e in events if e["kind"] == "part"], [x["stage"] for x in parts])
            self.assertEqual(state.journal_denials(events, "builder"), reports.stream_denials(path))
            self.assertEqual(sum(1 for e in events if e["kind"] == state.STREAM_FROZEN), 1)

    def test_the_view_answers_the_same_with_the_stream_gone(self):
        with project() as p:
            path = window(p)
            parts, _cost = reports.stream_parts(path)
            state.freeze_stream(state.journal_path(p.runs, "S-1"), path)
            os.remove(path)
            rows = cli.window_parts(state.journal_events(p.runs, "S-1"), "builder")
            self.assertEqual([r["stage"] for r in rows], list(dict.fromkeys(x["stage"] for x in parts)))
            for field in reports.USAGE_FIELDS:
                self.assertEqual(sum(r[field] for r in rows), sum(x[field] for x in parts), field)
            self.assertEqual(sum(r["denied"] for r in rows), len(reports.stream_denials(os.path.join(STREAMS, "claude-recorded.jsonl"))))

    def test_a_stream_is_frozen_only_once_its_process_has_ended(self):
        with project() as p:
            path = window(p)
            journal = state.journal_path(p.runs, "S-1")
            os.utime(path, (time.time() - 60, time.time() - 60))
            state.journal_append(p.runs, "S-1", "stage-start", "builder", "tool=claude")
            state.freeze_streams(journal)
            self.assertFalse(any(e["kind"] == "part" for e in state.journal_events(p.runs, "S-1")))
            state.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "input=1")
            state.freeze_streams(journal)
            self.assertTrue(any(e["kind"] == "part" for e in state.journal_events(p.runs, "S-1")))

    def test_a_retry_after_the_usage_limit_belongs_to_its_process(self):
        self.assertEqual(state.stream_process("builder.101500-limit1.out"), "builder")
        self.assertEqual(state.stream_process("review-ddd.101500.out"), "review-ddd")


JUDGE = ("## Verdict\nverdict: pass\n\n## Confirmed defects\n"
         "| Perspective | File:line | Severity | In plain words | Defect | Fix |\n|---|---|---|---|---|---|\n"
         "| ddd | A.java:3 | minor | a | domain-concept: no total | add it |\n")


def delivered_story(p, story_id, days_ago):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days_ago * 86400))
    return p.story(story_id, text=f"---\nid: {story_id}\nstatus: delivered\ndelivered: {stamp}\ndelivered_by: gate\n---\n"
                                  f"# {story_id}\n\n## Acceptance criteria\n- a (happy path): b\n")


def material(p):
    """A story run before the record: a stream its runner ended, its hand-overs, the test gate's tsv."""
    path = window(p)
    os.utime(path, (time.time() - 60, time.time() - 60))
    state.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "input=1", "seconds=40")
    p.handover("S-1", "plan", "# Plan\n\n## Open assumptions\n- the order\n")
    p.handover("S-1", "judge", JUDGE)
    p.evidence("S-1", state.INVARIANT_BREAKS, "Total\t1\tx.TotalTest#a\tkilled\n")
    return path


class Record(unittest.TestCase):

    def test_a_story_from_before_is_recorded_once_from_its_material(self):
        with project() as p:
            p.story("S-1")
            material(p)
            self.assertEqual(state.record_story(p.runs, "S-1"), {})
            self.assertIsNone(state.record_story(p.runs, "S-1"))
            events = state.journal_events(p.runs, "S-1")
            self.assertEqual([e["kind"] for e in events].count("record"), 1)
            from dca_factory import gate
            signals = gate.story_signals(p.runs, "S-1", [], "")
            self.assertEqual((signals["plan_open"], signals["rules"], signals["domain"]),
                             (1, {"killed": 1}, {"domain-concept": 1}))
            self.assertTrue(any(e["kind"] == "part" for e in events))

    def test_a_story_whose_process_still_runs_is_not_recorded_yet(self):
        with project() as p:
            p.story("S-1")
            window(p)
            self.assertIsNone(state.record_story(p.runs, "S-1"))
            self.assertIsNone(state.recorded(state.journal_events(p.runs, "S-1")))

    def test_material_that_is_gone_is_named_not_counted(self):
        with project() as p:
            p.story("S-1")
            state.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "seconds=40")
            state.journal_append(p.runs, "S-1", "gate", "plan", "exit=0", "by=runner")
            self.assertEqual(state.record_story(p.runs, "S-1"), {"unknown": "plan,streams"})
            from dca_factory import gate
            self.assertIsNone(gate.story_signals(p.runs, "S-1", [], "")["plan_open"])


class Prune(unittest.TestCase):

    def test_a_story_delivered_longer_ago_than_the_days_loses_its_streams_and_snapshots_only(self):
        with project() as p:
            delivered_story(p, "S-1", days_ago=8)
            material(p)
            p.evidence("S-1", "tree-after-builder.txt", "x\n")
            p.evidence("S-1", "gate-build.101500.txt", "gate:pass\n")
            parts_before = cli.window_parts(state.journal_events(p.runs, "S-1"), "builder") \
                if state.record_story(p.runs, "S-1") is not None else None
            self.assertEqual(state.prune_raw(p.runs, p.epics, days=7), [("S-1", 2)])
            folder = contract.evidence_dir(p.runs, "S-1")
            self.assertEqual(sorted(os.listdir(folder)),
                             ["gate-build.101500.txt", state.INVARIANT_BREAKS, "journal.tsv"])
            self.assertTrue(os.path.isfile(os.path.join(p.runs, "S-1", "plan.md")))
            self.assertEqual(cli.window_parts(state.journal_events(p.runs, "S-1"), "builder"), parts_before)
            self.assertEqual(state.prune_raw(p.runs, p.epics, days=7), [])

    def test_a_young_or_undelivered_story_keeps_its_material(self):
        with project() as p:
            delivered_story(p, "S-1", days_ago=2)
            material(p)
            self.assertEqual(state.prune_raw(p.runs, p.epics, days=7), [])
            p.story("S-1")
            self.assertEqual(state.prune_raw(p.runs, p.epics, days=0), [])
            self.assertTrue(state.raw_material(contract.evidence_dir(p.runs, "S-1")))

    def test_the_days_come_from_the_profile(self):
        self.assertEqual(state.keep_days({}), 7)
        self.assertEqual(state.keep_days({"evidence.keepDays": "30"}), 30)
        self.assertEqual(state.keep_days({"evidence.keepDays": "soon"}), 7)


if __name__ == "__main__":
    unittest.main()
