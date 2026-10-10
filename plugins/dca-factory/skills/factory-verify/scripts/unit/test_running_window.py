"""A shared window still running: its row shows what its stream says so far, before the tool reports its usage."""

import json
import os
import unittest
from datetime import datetime, timedelta, timezone

from support import contract, project, write
from dca_factory import cli


def stream(*stages):
    lines = []
    for n, stage in enumerate(stages):
        lines.append({"type": "assistant", "timestamp": f"2026-10-10T10:0{n}:00Z", "message": {
            "id": f"m{n}", "usage": {"input_tokens": 10, "cache_read_input_tokens": 100, "output_tokens": 2},
            "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": f".claude/skills/stage-{stage}/SKILL.md"}}]}})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


class RunningWindow(unittest.TestCase):

    def entry(self, runs=1, measured=0):
        return dict(runs=runs, measured=measured, seconds=0, tokens=0, input=0, cache_read=0, cache_write=0, output=0)

    def test_the_tokens_of_the_parts_and_with_live_the_time_since_it_began(self):
        with project() as p:
            write(os.path.join(contract.evidence_dir(p.runs, "S-1"), "builder.100000.out"), stream("plan", "test"))
            since = datetime.now(timezone.utc) - timedelta(minutes=3)
            entry = self.entry()
            cli.window_running(entry, p.runs, "S-1", dict(stage="builder", since=since), live=True)
            self.assertTrue(entry["running"])
            self.assertEqual((entry["input"], entry["cache_read"], entry["tokens"]), (20, 200, 224))
            self.assertGreaterEqual(entry["seconds"], 179)
            quiet = self.entry()
            cli.window_running(quiet, p.runs, "S-1", dict(stage="builder", since=since), live=False)
            self.assertEqual((quiet["tokens"], quiet["seconds"]), (224, 0))

    def test_a_window_whose_usage_is_in_or_a_stage_of_its_own_stays_as_the_journal_says(self):
        with project() as p:
            write(os.path.join(contract.evidence_dir(p.runs, "S-1"), "builder.100000.out"), stream("plan"))
            measured = self.entry(measured=1)
            cli.window_running(measured, p.runs, "S-1", dict(stage="builder", since=None), live=True)
            alone = self.entry()
            cli.window_running(alone, p.runs, "S-1", dict(stage="build", since=None), live=True)
            self.assertNotIn("running", measured)
            self.assertNotIn("running", alone)


if __name__ == "__main__":
    unittest.main()
