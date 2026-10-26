"""The journal is the story's record (WP-150): what a stream, a gate or a hand-over says about a story is a journal
line, written once, and the views read the journal alone — so the raw material can go."""

import json
import os
import shutil
import time
import unittest

from support import project
from dca_factory.delivery.adapter.outgoing.files import detail_files as detail
from dca_factory.delivery.application.status import show_story
from dca_factory.delivery.domain.model import usage
from dca_factory.delivery.adapter.outgoing.tools import streams
from dca_factory.delivery.adapter.outgoing.files import journal_files as journals
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles
from dca_factory.delivery.adapter.outgoing.files import usage_files
from dca_factory.delivery.adapter.outgoing.files import windows
from dca_factory.delivery.adapter.outgoing.files import story_record
from dca_factory.delivery.adapter.outgoing.files import stream_records
from dca_factory.delivery.adapter.outgoing.files import status_facts

STREAMS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "streams")
SECOND = "2026-10-10T10:00:00Z"


def window(p, name="builder.100000.out", source="claude-recorded.jsonl"):
    """A shared builder's recorded stream beside S-1's journal."""
    path = os.path.join(profiles.evidence_dir(p.runs, "S-1"), name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy(os.path.join(STREAMS, source), path)
    return path


class FrozenStream(unittest.TestCase):

    def test_a_streams_parts_and_denials_are_journal_lines_once(self):
        with project() as p:
            path = window(p)
            journal = journals.journal_path(p.runs, "S-1")
            self.assertTrue(stream_records.freeze_stream(journal, path))
            self.assertFalse(stream_records.freeze_stream(journal, path))
            events = journals.journal_events(p.runs, "S-1")
            parts, _cost = streams.stream_parts(path)
            self.assertEqual([e["name"] for e in events if e["kind"] == "part"], [x["stage"] for x in parts])
            self.assertEqual(usage_files.journal_denials(events, "builder"), streams.stream_denials(path))
            self.assertEqual(sum(1 for e in events if e["kind"] == stream_records.STREAM_FROZEN), 1)

    def test_the_view_answers_the_same_with_the_stream_gone(self):
        with project() as p:
            path = window(p)
            parts, _cost = streams.stream_parts(path)
            stream_records.freeze_stream(journals.journal_path(p.runs, "S-1"), path)
            os.remove(path)
            rows = detail.window_parts(journals.journal_events(p.runs, "S-1"), "builder")
            self.assertEqual([r["stage"] for r in rows], list(dict.fromkeys(x["stage"] for x in parts)))
            for field in usage.USAGE_FIELDS:
                self.assertEqual(sum(r[field] for r in rows), sum(x[field] for x in parts), field)
            self.assertEqual(sum(r["denied"] for r in rows), len(streams.stream_denials(os.path.join(STREAMS, "claude-recorded.jsonl"))))

    def test_a_stream_is_frozen_only_once_its_process_has_ended_by_the_journal_never_by_its_file_time(self):
        with project() as p:
            path = window(p)
            journal = journals.journal_path(p.runs, "S-1")
            os.utime(path, (time.time() + 3600, time.time() + 3600))      # a move or a copy sets it anew
            journals.journal_append(p.runs, "S-1", "stage-start", "builder", "tool=claude")
            stream_records.freeze_streams(journal)
            self.assertFalse(any(e["kind"] == "part" for e in journals.journal_events(p.runs, "S-1")))
            journals.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "input=1")
            stream_records.freeze_streams(journal)
            self.assertTrue(any(e["kind"] == "part" for e in journals.journal_events(p.runs, "S-1")))

    def test_a_retry_after_the_usage_limit_belongs_to_its_process(self):
        self.assertEqual(stream_records.stream_process("builder.101500-limit1.out"), "builder")
        self.assertEqual(stream_records.stream_process("review-ddd.101500.out"), "review-ddd")


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
    journals.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "input=1", "seconds=40")
    p.handover("S-1", "plan", "# Plan\n\n## Open assumptions\n- the order\n")
    p.handover("S-1", "judge", JUDGE)
    p.evidence("S-1", story_record.INVARIANT_BREAKS, "Total\t1\tx.TotalTest#a\tkilled\n")
    return path


class Record(unittest.TestCase):

    def test_a_story_from_before_is_recorded_once_from_its_material(self):
        with project() as p:
            p.story("S-1")
            material(p)
            self.assertEqual(story_record.record_story(p.runs, "S-1"), {})
            self.assertIsNone(story_record.record_story(p.runs, "S-1"))
            events = journals.journal_events(p.runs, "S-1")
            self.assertEqual([e["kind"] for e in events].count("record"), 1)
            from dca_factory import gate
            signals = status_facts.story_signals(p.runs, "S-1", [], "")
            self.assertEqual((signals["plan_open"], signals["rules"], signals["domain"]),
                             (1, {"killed": 1}, {"domain-concept": 1}))
            self.assertTrue(any(e["kind"] == "part" for e in events))

    def test_a_story_whose_process_still_runs_is_not_recorded_yet(self):
        with project() as p:
            p.story("S-1")
            window(p)
            self.assertIsNone(story_record.record_story(p.runs, "S-1"))
            self.assertIsNone(story_record.recorded(journals.journal_events(p.runs, "S-1")))

    def test_material_that_is_gone_is_named_not_counted(self):
        with project() as p:
            p.story("S-1")
            journals.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude", "seconds=40")
            journals.journal_append(p.runs, "S-1", "gate", "plan", "exit=0", "by=runner")
            self.assertEqual(story_record.record_story(p.runs, "S-1"), {"unknown": "plan,streams"})
            from dca_factory import gate
            self.assertIsNone(status_facts.story_signals(p.runs, "S-1", [], "")["plan_open"])


class Prune(unittest.TestCase):

    def test_a_story_delivered_longer_ago_than_the_days_loses_its_streams_and_snapshots_only(self):
        with project() as p:
            delivered_story(p, "S-1", days_ago=8)
            material(p)
            p.evidence("S-1", "tree-after-builder.txt", "x\n")
            p.evidence("S-1", "gate-build.101500.txt", "gate:pass\n")
            parts_before = detail.window_parts(journals.journal_events(p.runs, "S-1"), "builder") \
                if story_record.record_story(p.runs, "S-1") is not None else None
            self.assertEqual(story_record.prune_raw(p.runs, p.epics, days=7), [("S-1", 2)])
            folder = profiles.evidence_dir(p.runs, "S-1")
            self.assertEqual(sorted(os.listdir(folder)),
                             ["gate-build.101500.txt", story_record.INVARIANT_BREAKS, "journal.tsv"])
            self.assertTrue(os.path.isfile(os.path.join(p.runs, "S-1", "plan.md")))
            self.assertEqual(detail.window_parts(journals.journal_events(p.runs, "S-1"), "builder"), parts_before)
            self.assertEqual(story_record.prune_raw(p.runs, p.epics, days=7), [])

    def test_a_young_or_undelivered_story_keeps_its_material(self):
        with project() as p:
            delivered_story(p, "S-1", days_ago=2)
            material(p)
            self.assertEqual(story_record.prune_raw(p.runs, p.epics, days=7), [])
            p.story("S-1")
            self.assertEqual(story_record.prune_raw(p.runs, p.epics, days=0), [])
            self.assertTrue(story_record.raw_material(profiles.evidence_dir(p.runs, "S-1")))

    def test_the_days_come_from_the_profile(self):
        self.assertEqual(story_record.keep_days({}), 7)
        self.assertEqual(story_record.keep_days({"evidence.keepDays": "30"}), 30)
        self.assertEqual(story_record.keep_days({"evidence.keepDays": "soon"}), 7)


def resumed_builder(*commands):
    """A builder resumed after a question: it loads no stage's skill, only runs the skeletons and the gates."""
    lines = []
    for n, command in enumerate(commands):
        lines.append({"type": "assistant", "timestamp": f"2026-10-10T10:{n:02d}:00Z", "message": {
            "id": f"m{n}", "usage": {"input_tokens": 10, "output_tokens": 2},
            "content": [{"type": "tool_use", "id": f"t{n}", "name": "Bash", "input": {"command": command}}]}})
    lines.append({"type": "result", "total_cost_usd": 1.0})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


RESUMED = ("cat .claude/skills/factory-run/reference/stage-common.md",
           "python3 .agents/factory/factory-cli.py --plan-skeleton S-1",
           "python3 .agents/factory/story-gate.py --story S-1 --stage plan --brief",
           "python3 .agents/factory/factory-cli.py --files-skeleton S-1 test",
           "python3 .agents/factory/story-gate.py --story S-1 --stage test --brief",
           "python3 .agents/factory/factory-cli.py --files-skeleton S-1 build",
           "python3 .agents/factory/story-gate.py --story S-1 --stage build --brief",
           "python3 .agents/factory/story-gate.py --story S-1 --stage test --brief",
           "python3 .agents/factory/story-gate.py --story S-1 --stage tidy --brief")


class ResumedBuilder(unittest.TestCase):
    """0.90.1: a part begins at a stage's skeleton or gate too — a resumed builder loads no stage's skill."""

    def test_its_stages_are_read_from_the_skeletons_and_the_gates_and_an_earlier_gate_does_not_go_back(self):
        with project() as p:
            path = p.evidence("S-1", "builder.100000.out", resumed_builder(*RESUMED))
            self.assertEqual([x["stage"] for x in streams.stream_parts(path)[0]], ["plan", "test", "build", "tidy"])

    def test_a_stream_an_older_reading_froze_is_frozen_again_and_read_once(self):
        with project() as p:
            path = p.evidence("S-1", "builder.100000.out", resumed_builder(*RESUMED))
            journal = journals.journal_path(p.runs, "S-1")
            journals.journal_append(p.runs, "S-1", "usage", "builder", "tool=claude")
            # what 0.90.0 wrote: one part, the stream line without a version
            journals.journal_append(p.runs, "S-1", "stream", "builder.100000.out", "process=builder", "parts=0", "denied=0")
            self.assertTrue(stream_records.parts_incomplete(journals.journal_events(p.runs, "S-1"), "builder"))
            stream_records.freeze_streams(journal)
            stream_records.freeze_streams(journal)
            events = journals.journal_events(p.runs, "S-1")
            self.assertEqual([r["stage"] for r in stream_records.journal_parts(events, "builder")], ["plan", "test", "build", "tidy"])
            self.assertEqual(sum(r["runs"] for r in stream_records.journal_parts(events, "builder")), 4)
            self.assertEqual(sum(1 for e in events if e["kind"] == "stream"), 2)
            self.assertFalse(stream_records.parts_incomplete(events, "builder"))

    def test_a_run_frozen_with_no_part_whose_stream_is_gone_says_the_parts_are_incomplete(self):
        with project() as p:
            journals.journal_append(p.runs, "S-1", "part", "plan", "process=builder", "stream=builder.100000.out", "seconds=9")
            journals.journal_append(p.runs, "S-1", "stream", "builder.100000.out", "process=builder", "parts=1", "denied=0")
            events = journals.journal_events(p.runs, "S-1")
            self.assertEqual([r["stage"] for r in stream_records.journal_parts(events, "builder")], ["plan"])
            self.assertFalse(stream_records.parts_incomplete(events, "builder"))      # its stages' skills were seen
            journals.journal_append(p.runs, "S-1", "stream", "builder.110000.out", "process=builder", "parts=0", "denied=0")
            self.assertTrue(stream_records.parts_incomplete(journals.journal_events(p.runs, "S-1"), "builder"))


class OneWayToRead(unittest.TestCase):
    """WP-150 D: after the migration the readers know the journal alone — no stream or hand-over parser in them."""

    def test_the_readers_hold_no_stream_or_hand_over_parser(self):
        import inspect
        from dca_factory import gate
        for reader in (status_facts.story_signals, detail.window_parts):
            text = inspect.getsource(reader)
            for parser in ("stream_parts", "stream_denials", "plan.md", "judge.md", "INVARIANT_BREAKS", "read_text"):
                self.assertNotIn(parser, text, f"{reader.__name__} reads {parser}")
        model = inspect.getsource(show_story)
        self.assertNotIn("stream_denials", model)
        self.assertNotIn(".out", model)


if __name__ == "__main__":
    unittest.main()
