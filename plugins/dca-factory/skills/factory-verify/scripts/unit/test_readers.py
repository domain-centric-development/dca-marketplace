"""One reader per tool (WP-95): every tool's recorded stream read for its usage, its parts, its denials and its
`follow` lines through the same common events — and the names of the tools taken from the records alone."""

import os
import unittest

from support import contract, reports
from dca_factory import cli, gate, tools

STREAMS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "streams")


def stream(name):
    return os.path.join(STREAMS, name)


def raw(name):
    with open(stream(name), encoding="utf-8") as handle:
        return handle.read()


class EveryTool(unittest.TestCase):

    def test_each_record_names_a_reader(self):
        for tool in tools.TOOLS:
            self.assertIn(tool.usage, reports.READERS, tool.name)

    def test_the_format_is_found_from_the_stream_alone(self):
        for name, fmt in (("claude-stream.jsonl", "claude-json"), ("codex-stream.jsonl", "codex-jsonl"),
                          ("opencode-stream.jsonl", "opencode-json")):
            self.assertEqual(reports.reader_of(raw(name)).fmt, fmt)

    def test_the_usage_of_each_stream(self):
        usage, text = reports.parse_usage("claude-json", stream("claude-stream.jsonl"))
        self.assertEqual((usage["output"], usage["cost"]), (200, "0.4200"))
        usage, text = reports.parse_usage("codex-jsonl", stream("codex-stream.jsonl"))
        self.assertEqual((usage["input"], usage["cache_read"], usage["output"]), (700, 3500, 200))
        self.assertEqual(text, "Plan written.")
        usage, _text = reports.parse_usage("opencode-json", stream("opencode-stream.jsonl"))
        self.assertEqual((usage["input"], usage["output"], usage["cost"]), (2400, 170, "0.0300"))

    def test_the_parts_of_a_shared_process_for_every_tool(self):
        for name in ("claude-stream.jsonl", "codex-stream.jsonl", "opencode-stream.jsonl"):
            parts, _cost = reports.stream_parts(stream(name))
            self.assertEqual([p["stage"] for p in parts], ["plan", "test"], name)
            self.assertTrue(all(p["weight"] > 0 for p in parts), (name, parts))

    def test_a_skill_read_with_the_shell_begins_the_part_like_the_skill_tool(self):
        parts, cost = reports.stream_parts(stream("claude-stream.jsonl"))
        self.assertEqual(cost, 0.42)
        self.assertEqual(parts[1]["stage"], "test")

    def test_denials_come_from_the_format_that_reports_them(self):
        denied = reports.stream_denials(stream("claude-stream.jsonl"))
        self.assertEqual(denied, [{"stage": "test", "tool": "Bash", "command": "git push origin main"}])
        self.assertEqual(reports.stream_denials(stream("codex-stream.jsonl")), [])

    def test_follow_shows_every_tool_the_same_way(self):
        lines, ended = cli.follow_lines(raw("claude-stream.jsonl"))
        self.assertTrue(ended)
        self.assertIn("── plan", lines)
        self.assertIn("✗ denied: Permission to use Bash has been denied.", lines)
        self.assertTrue(lines[-1].startswith("■ done — 4 turns, $0.42"))
        for name in ("codex-stream.jsonl", "opencode-stream.jsonl"):
            lines, ended = cli.follow_lines(raw(name))
            self.assertIn("── plan", lines, name)
            self.assertIn("── test", lines, name)
            self.assertTrue(any(line.startswith("✗ ") for line in lines), (name, lines))
            self.assertTrue(ended, name)


class RecordedStreams(unittest.TestCase):
    """Streams recorded from the real binaries (claude 2.x stream-json, codex exec --json 0.153, opencode run --format
    json 2.0.20 on a local model), each reading a stage's SKILL.md and writing one file."""

    def test_each_recorded_stream_shows_its_plan_part_its_usage_and_its_follow_lines(self):
        for tool, fmt in (("claude", "claude-json"), ("codex", "codex-jsonl"), ("opencode", "opencode-json")):
            path = stream(f"{tool}-recorded.jsonl")
            self.assertEqual(reports.reader_of(raw(f"{tool}-recorded.jsonl")).fmt, fmt)
            self.assertEqual([p["stage"] for p in reports.stream_parts(path)[0]], ["plan"], tool)
            usage, _text = reports.parse_usage(fmt, path)
            self.assertGreater(usage["output"], 0, tool)
            lines, ended = cli.follow_lines(raw(f"{tool}-recorded.jsonl"))
            self.assertIn("── plan", lines, tool)
            self.assertTrue(ended and lines[-1].startswith("■ done"), (tool, lines[-3:]))

    def test_the_recorded_claude_stream_names_its_denials(self):
        denied = reports.stream_denials(stream("claude-recorded.jsonl"))
        self.assertEqual(len(denied), 2)
        self.assertTrue(all(d["stage"] == "plan" for d in denied))


class UsageLimit(unittest.TestCase):
    """#161: the tool's usage limit read from its own output — recorded from `claude -p` on 2026-10-13 in a shop's run;
    no other tool's output at the limit is recorded yet, so their readers name none."""

    def test_the_recorded_claude_stream_names_the_limit_and_its_reset(self):
        limited = reports.stream_limit(stream("claude-limit-recorded.jsonl"))
        self.assertEqual(limited["until"], 1791868200)
        self.assertIn("session limit", limited["text"])

    def test_a_claude_result_without_the_limit_names_none(self):
        self.assertIsNone(reports.stream_limit(stream("claude-recorded.jsonl")))
        self.assertIsNone(reports.stream_limit(stream("claude-stream.jsonl")))

    def test_the_limit_without_a_rejected_event_has_no_reset(self):
        text = "\n".join(line for line in raw("claude-limit-recorded.jsonl").splitlines() if "rejected" not in line)
        limited = reports.READERS["claude-json"].limit(text)
        self.assertIsNone(limited["until"])

    def test_the_other_tools_name_no_limit(self):
        for name in ("codex-recorded.jsonl", "opencode-recorded.jsonl"):
            self.assertIsNone(reports.stream_limit(stream(name)), name)


class NamesFromTheRecords(unittest.TestCase):
    """A list of the tools beside `TOOLS` drifts from it: each one is held to the records."""

    def test_the_model_keys_know_exactly_the_recorded_tools(self):
        self.assertEqual(set(gate.MODEL_TOOLS), {t.name for t in tools.TOOLS})

    def test_a_worktree_links_every_recorded_skill_folder(self):
        self.assertTrue({t.skills for t in tools.TOOLS} <= set(contract.WORKTREE_LINKED))

    def test_the_tool_folders_a_change_check_leaves_out_are_the_records(self):
        self.assertEqual(set(gate.TOOL_FOLDERS), {"/" + t.skills.split("/")[0] + "/" for t in tools.TOOLS})


if __name__ == "__main__":
    unittest.main()
