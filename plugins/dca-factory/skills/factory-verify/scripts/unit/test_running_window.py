"""A shared window still running: its row shows what its stream says so far, before the tool reports its usage."""

import json
import os
import unittest
from datetime import datetime, timedelta, timezone

from support import project, write
from dca_factory.delivery.adapter.outgoing.pipeline.stage_rows import stage_windows
from dca_factory.delivery.adapter.outgoing.files.detail_files import DetailFactFiles
from dca_factory.delivery.application.status.show_story import window_running
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles


def stream(*stages):
    lines = []
    for n, stage in enumerate(stages):
        lines.append({"type": "assistant", "timestamp": f"2026-10-10T10:0{n}:00Z", "message": {
            "id": f"m{n}", "usage": {"input_tokens": 10, "cache_read_input_tokens": 100, "output_tokens": 2},
            "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": f".claude/skills/stage-{stage}/SKILL.md"}}]}})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


def running(entry, runs, story, moving, live):
    """The row of a shared window still running, its stream read where the factory reads it."""
    window_running(entry, moving, stage_windows(), lambda: DetailFactFiles("", runs).stream_now(story, moving["stage"]),
                   datetime.now(timezone.utc), live)


class RunningWindow(unittest.TestCase):

    def entry(self, runs=1, measured=0):
        return dict(runs=runs, measured=measured, seconds=0, tokens=0, input=0, cache_read=0, cache_write=0, output=0)

    def test_the_tokens_of_the_parts_and_with_live_the_time_since_it_began(self):
        with project() as p:
            write(os.path.join(profiles.evidence_dir(p.runs, "S-1"), "builder.100000.out"), stream("plan", "test"))
            since = datetime.now(timezone.utc) - timedelta(minutes=3)
            entry = self.entry()
            running(entry, p.runs, "S-1", dict(stage="builder", since=since), live=True)
            self.assertTrue(entry["running"])
            self.assertEqual((entry["input"], entry["cache_read"], entry["tokens"]), (20, 200, 224))
            self.assertGreaterEqual(entry["seconds"], 179)
            quiet = self.entry()
            running(quiet, p.runs, "S-1", dict(stage="builder", since=since), live=False)
            self.assertEqual((quiet["tokens"], quiet["seconds"]), (224, 0))

    def test_a_window_whose_usage_is_in_or_a_stage_of_its_own_stays_as_the_journal_says(self):
        with project() as p:
            write(os.path.join(profiles.evidence_dir(p.runs, "S-1"), "builder.100000.out"), stream("plan"))
            measured = self.entry(measured=1)
            running(measured, p.runs, "S-1", dict(stage="builder", since=None), live=True)
            alone = self.entry()
            running(alone, p.runs, "S-1", dict(stage="build", since=None), live=True)
            self.assertNotIn("running", measured)
            self.assertNotIn("running", alone)


if __name__ == "__main__":
    unittest.main()


class CourseFacts:
    """Just what a running story's course reads: its kind and the stages of that kind."""

    def story_kind(self, path):
        return "task"

    def stage_course(self, kind):
        return {"task": ("plan", "build", "tidy", "judge", "document")}[kind]


class TheCourseOfARunningStory(unittest.TestCase):
    """The page draws a running story as its course: each stage of its kind done, now or open."""

    def course(self, stage, part="", at="now"):
        from dca_factory.delivery.application.status.show_status import ShowStatusUseCase
        use_case = ShowStatusUseCase(CourseFacts(), None, None)
        return [(c["stage"], c["state"]) for c in use_case._course("s", {"path": "story.md"}, stage, part,
                                                                       {"builder": ("test", "build", "tidy")}, at=at)]

    def test_a_stopped_story_stands_stopped_at_the_stage_it_goes_on_from(self):
        self.assertEqual([("plan", "done"), ("build", "done"), ("tidy", "done"), ("judge", "done"), ("document", "stopped")],
                         self.course("document", at="stopped"))

    def test_the_stages_before_the_running_one_are_done_and_the_rest_open(self):
        self.assertEqual([("plan", "done"), ("build", "done"), ("tidy", "done"), ("judge", "now"), ("document", "open")],
                         self.course("judge"))

    def test_a_shared_window_is_at_the_part_it_runs_or_at_its_first_stage_of_the_kind(self):
        self.assertEqual("now", dict(self.course("builder", "tidy"))["tidy"])
        self.assertEqual("open", dict(self.course("builder"))["build"])     # its first stage, test, is not a task's


class TheDeliveredCurve(unittest.TestCase):
    """What all deliveries up to one cost together, oldest first; an unpriced one adds tokens, not cost."""

    def test_the_sums_grow_with_each_delivery_in_its_order(self):
        from dca_factory.delivery.application.status.show_status import ShowStatusUseCase
        row = lambda story, at, tokens, cost: dict(story=story, title=story, delivered=at, tokens=tokens, cost=cost,
                                                   priced=1 if cost is not None else 0)
        curve = ShowStatusUseCase._curve([row("b", "2026-10-02T10:00:00Z", 300, None),
                                          row("a", "2026-10-01T10:00:00Z", 100, 1.5),
                                          row("c", "2026-10-03T10:00:00Z", 50, 2.25)])
        self.assertEqual([("a", 100, 1.5, 1), ("b", 400, 1.5, 1), ("c", 450, 3.75, 2)],
                         [(c["story"], c["tokens_total"], c["cost_total"], c["priced_total"]) for c in curve])
