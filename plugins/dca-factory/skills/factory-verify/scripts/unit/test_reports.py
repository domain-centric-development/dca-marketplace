"""The report readers: which tests ran and how (JUnit XML, TRX), and what a stage cost (the tools' usage streams)."""

import json
import os
import tempfile
import unittest

from support import reports, write

JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.WidgetTest" tests="5">
  <testcase classname="com.example.WidgetTest" name="showsIt" time="0.1"/>
  <testcase classname="com.example.WidgetTest" name="hidesIt"><failure message="no"/></testcase>
  <testcase classname="com.example.WidgetTest" name="breaks"><error message="boom"/></testcase>
  <testcase classname="com.example.WidgetTest" name="later"><skipped/></testcase>
  <testcase classname="com.example.WidgetTest" name="counts[1]"/>
  <testcase classname="com.example.WidgetTest" name="counts[2]"><failure/></testcase>
  <testcase classname="com.example.WidgetTest" name="counts(int)[3]"/>
  <testcase classname="com.example.WidgetTest" name="Widget is shown to a visitor"/>
</testsuite>
"""

TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult testName="Example.Widgets.WidgetTests.ShowsIt" outcome="Passed"/>
    <UnitTestResult testName="Example.Widgets.WidgetTests.HidesIt" outcome="Failed"/>
    <UnitTestResult testName="Example.Widgets.WidgetTests.Later" outcome="NotExecuted"/>
    <UnitTestResult testName="Example.Widgets.WidgetTests.Odd" outcome="Inconclusive"/>
  </Results>
</TestRun>
"""

#: Playwright's JUnit reporter: the spec file as the class, the title path as the name.
PLAYWRIGHT_JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="widget.spec.ts">
  <testcase name="Widgets › shows the thing. Fast" classname="e2e/widget.spec.ts"/>
  <testcase name="Widgets › hides it" classname="e2e/widget.spec.ts"><failure/></testcase>
</testsuite></testsuites>
"""


class Reports(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def file(self, name, text):
        return write(os.path.join(self.folder.name, name), text)


class ExecutedTests(Reports):

    def test_junit_cases_read_as_passed_failed_and_skipped(self):
        ran = reports.executed_tests([self.file("TEST-widget.xml", JUNIT)])
        cls = "com.example.WidgetTest"
        self.assertEqual({m: ran[(cls, m)] for m in ("showsIt", "hidesIt", "breaks", "later")},
                         {"showsIt": "passed", "hidesIt": "failed", "breaks": "failed", "later": "skipped"})

    def test_the_cases_of_one_parametrised_test_merge_and_failed_wins(self):
        ran = reports.executed_tests([self.file("TEST-widget.xml", JUNIT)])
        self.assertEqual(ran[("com.example.WidgetTest", "counts")], "failed")
        self.assertNotIn(("com.example.WidgetTest", "counts[1]"), ran)

    def test_trx_names_split_into_class_and_method(self):
        ran = reports.executed_tests([self.file("run.trx", TRX)])
        self.assertEqual(ran, {("Example.Widgets.WidgetTests", "ShowsIt"): "passed",
                               ("Example.Widgets.WidgetTests", "HidesIt"): "failed",
                               ("Example.Widgets.WidgetTests", "Later"): "skipped",
                               ("Example.Widgets.WidgetTests", "Odd"): "failed"})

    def test_a_file_that_is_no_xml_report_is_skipped(self):
        broken = self.file("broken.xml", "<testsuite><testcase name='x'>")
        playwright_json = self.file("results.json", json.dumps({"suites": [{"specs": [{"title": "shows it"}]}]}))
        self.assertEqual(reports.executed_tests([broken, playwright_json, "/no/such/report.xml"]), {})

    def test_reported_names_keep_a_title_whole(self):
        names = reports.reported_names([self.file("playwright.xml", PLAYWRIGHT_JUNIT), self.file("run.trx", TRX)])
        self.assertEqual(names["Widgets › shows the thing. Fast"], "passed")
        self.assertEqual(names["Widgets › hides it"], "failed")
        self.assertEqual(names["Example.Widgets.WidgetTests.Odd"], "skipped")


class OutcomeFor(Reports):

    def ran(self):
        return reports.executed_tests([self.file("TEST-widget.xml", JUNIT)])

    def test_a_selector_is_found_by_its_method_name(self):
        self.assertEqual(reports.outcome_for(self.ran(), "com.example.WidgetTest", "hidesIt"), ("failed", "by name"))

    def test_a_display_name_is_the_second_key(self):
        outcome, how = reports.outcome_for(self.ran(), "com.example.WidgetTest", "showsWidget",
                                           display="Widget is shown to a visitor")
        self.assertEqual(outcome, "passed")
        self.assertIn("by the display name", how)

    def test_a_sibling_of_the_class_never_stands_in_for_the_test(self):
        outcome, how = reports.outcome_for(self.ran(), "com.example.WidgetTest", "missing")
        self.assertIsNone(outcome)
        self.assertIn("none is named 'missing'", how)

    def test_a_class_of_the_same_name_in_another_package_is_not_this_one(self):
        self.assertEqual(reports.outcome_for(self.ran(), "org.other.WidgetTest", "showsIt"), (None, ""))

    def test_the_display_name_is_read_from_the_declaration(self):
        path = self.file("WidgetTest.java", 'class WidgetTest {\n  @Test\n  @DisplayName("Say \\"hi\\"")\n'
                                            '  void greets() {}\n  @Test\n  void plain() {}\n}\n')
        self.assertEqual(reports.display_name_of(path, "greets"), 'Say "hi"')
        self.assertIsNone(reports.display_name_of(path, "plain"))
        csharp = self.file("WidgetTests.cs", '[Fact(DisplayName = "Shows it")]\npublic void ShowsIt() {}\n')
        self.assertEqual(reports.display_name_of(csharp, "ShowsIt"), "Shows it")


class Usage(Reports):

    RESULT = {"type": "result", "result": "done", "total_cost_usd": 0.12345,
              "modelUsage": {"claude-a": {"inputTokens": 10, "cacheReadInputTokens": 100,
                                          "cacheCreationInputTokens": 20, "outputTokens": 5},
                             "claude-b": {"inputTokens": 1, "outputTokens": 2}}}

    def test_a_claude_result_sums_its_models(self):
        usage, text = reports.parse_usage("claude-json", self.file("out.json", json.dumps(self.RESULT)))
        self.assertEqual(usage, {"model": "claude-a,claude-b", "input": 11, "cache_read": 100, "cache_write": 20,
                                 "output": 7, "cost": "0.1235"})
        self.assertEqual(text, "done")

    def test_a_claude_stream_is_read_from_its_result_event(self):
        stream = "\n".join(json.dumps(e) for e in (
            {"type": "system"}, {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}},
            self.RESULT))
        usage, text = reports.parse_usage("claude-json", self.file("out.jsonl", stream))
        self.assertEqual((usage["input"], text), (11, "done"))

    def test_a_stream_cut_off_before_its_result_has_no_usage_and_its_last_answer(self):
        stream = "\n".join(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}})
                           for t in ("first", "last"))
        self.assertEqual(reports.parse_usage("claude-json", self.file("out.jsonl", stream)), (None, "last"))
        self.assertEqual(reports.parse_usage("claude-json", self.file("raw.txt", "command not found")),
                         (None, "command not found"))

    def test_codex_counts_the_cached_part_of_its_input_apart(self):
        stream = "\n".join(json.dumps(e) for e in (
            {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 7}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}}))
        self.assertEqual(reports.parse_usage("codex-jsonl", self.file("codex.jsonl", stream)),
                         ({"input": 50, "cache_read": 60, "cache_write": 0, "output": 10}, "done"))

    def test_opencode_sums_its_steps_and_a_zero_cost_is_no_price(self):
        step = {"type": "step_finish", "part": {"tokens": {"input": 5, "output": 2, "reasoning": 1,
                                                           "cache": {"read": 3, "write": 4}}, "cost": 0}}
        stream = "\n".join(json.dumps(e) for e in (
            {"type": "text", "part": {"text": "do"}}, step, {"type": "text", "part": {"text": "ne"}}, step))
        self.assertEqual(reports.parse_usage("opencode-json", self.file("oc.jsonl", stream)),
                         ({"input": 10, "cache_read": 6, "cache_write": 8, "output": 6}, "done"))

    def test_an_unknown_format_reports_nothing(self):
        self.assertEqual(reports.parse_usage("other", self.file("x.txt", "raw")), (None, "raw"))
        self.assertEqual(reports.parse_usage("claude-json", "/no/such/file"), (None, ""))

    def test_a_time_without_a_zone_is_utc(self):
        self.assertEqual(reports.parse_time("2026-10-10T10:00:00Z"), reports.parse_time("2026-10-10T10:00:00"))
        self.assertIsNone(reports.parse_time("yesterday"))
        self.assertIsNone(reports.parse_time(""))


def answer(message_id, at, usage, skill=None, text=""):
    content = [{"type": "text", "text": text}] if text else []
    if skill:
        content.append({"type": "tool_use", "name": "Skill", "input": {"skill": skill}})
    return {"type": "assistant", "timestamp": at, "message": {"id": message_id, "content": content, "usage": usage}}


class StreamParts(Reports):

    def stream(self, *events):
        return self.file("builder.jsonl", "\n".join(json.dumps(e) for e in events) + "\n")

    def test_a_shared_window_splits_into_the_stages_it_loaded(self):
        path = self.stream(
            answer("m1", "2026-10-10T10:00:00Z", {"input_tokens": 10, "output_tokens": 1}, skill="dca-factory:stage-plan"),
            answer("m1", "2026-10-10T10:00:01Z", {"input_tokens": 10, "cache_read_input_tokens": 50, "output_tokens": 1},
                   text="aaaa"),
            answer("m2", "2026-10-10T10:01:00Z", {"input_tokens": 20, "output_tokens": 1}, skill="stage-test"),
            answer("m3", "2026-10-10T10:02:00Z", {"input_tokens": 5, "cache_creation_input_tokens": 8,
                                                  "cache_creation": {"ephemeral_1h_input_tokens": 8}}, text="bbbb"),
            {"type": "result", "total_cost_usd": 1.5, "modelUsage": {"m": {"outputTokens": 100}}})
        parts, cost = reports.stream_parts(path)
        self.assertEqual(cost, 1.5)
        self.assertEqual([p["stage"] for p in parts], ["plan", "test"])
        plan, test = parts
        self.assertEqual((plan["input"], plan["cache_read"], test["input"], test["cache_write"]), (10, 50, 25, 8))
        self.assertEqual(plan["end"], test["start"])
        self.assertEqual(plan["output"] + test["output"], 100)

    def test_a_stream_that_loads_no_stage_has_no_parts(self):
        path = self.stream(answer("m1", "2026-10-10T10:00:00Z", {"input_tokens": 1}, text="hi"),
                           {"type": "result", "total_cost_usd": 0.5})
        self.assertEqual(reports.stream_parts(path), ([], 0.5))

    def test_a_stream_that_is_gone_has_no_parts(self):
        self.assertEqual(reports.stream_parts("/no/such/stream"), ([], None))


if __name__ == "__main__":
    unittest.main()
