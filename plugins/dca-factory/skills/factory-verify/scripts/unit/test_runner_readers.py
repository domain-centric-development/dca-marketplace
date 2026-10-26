"""What the runner reads in its own process: the profile and the places as a cli started where it stands would."""

import os
import tempfile
import types
import unittest

from support import project, state, write
from dca_factory import runner
from dca_factory.delivery.adapter.outgoing.tools import agents
from dca_factory.delivery.adapter.outgoing.files import journal_files as journal
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles


def a_run(p):
    options = types.SimpleNamespace(max_stages=0, story_budget=0, builder="shared", verifier="shared", parallel=0)
    return runner.Run(options, p.root, ".dca-factory/runs", worker="unit:host:1")


class Readers(unittest.TestCase):

    def tearDown(self):
        os.environ.pop("FACTORY_HOME", None)

    def test_the_profile_is_read_on_every_question(self):
        with project() as p:
            profile = write(os.path.join(p.root, profiles.PROFILE_FILE), "model.claude: sonnet\n")
            run = a_run(p)
            self.assertEqual(run.tools.model_key("claude", "build"), "sonnet")
            write(profile, "model.claude: sonnet\nmodel.claude.build: opus\n")
            self.assertEqual(run.tools.model_key("claude", "build:2"), "opus")
            self.assertEqual(run.tools.model_key("codex", "build"), "")

    def test_in_a_worktree_the_places_are_the_main_checkouts_and_back_home_they_are_relative_again(self):
        with project() as p, tempfile.TemporaryDirectory() as tree:
            write(os.path.join(p.root, profiles.PROFILE_FILE), "carrier.guard: the-guard\n")
            p.run_file("S-1", "judge.md", "## Verdict\nverdict: `approved`\n")
            run = a_run(p)
            os.chdir(tree)
            os.environ["FACTORY_HOME"] = p.root
            try:
                self.assertIn("the-guard", run.guard_sentence())
                self.assertEqual(profiles.place("runs"), p.root.replace(os.sep, "/") + "/.dca-factory/runs")   # places use /
                self.assertEqual(run.verdict_of("S-1"), "approved")
                run.journal_line("S-1", "2026-10-10T10:00:00Z\tnote\t-\twhy=from-the-tree")
                self.assertEqual([e["kind"] for e in journal.journal_events(p.runs, "S-1")], ["note"])
            finally:
                # out of the tree before it is removed: Windows refuses to delete the working directory
                os.chdir(p.root)
                os.environ.pop("FACTORY_HOME")
            run.profile()
            self.assertEqual(profiles.place("runs"), ".dca-factory/runs")

    def test_what_a_story_and_its_files_say(self):
        with project() as p:
            p.story("S-1", status="adopted")
            p.story("S-2", status="approved")
            run = a_run(p)
            self.assertEqual(run.kind_of("S-1"), "adopt")
            self.assertEqual(run.kind_of("S-9"), "story")
            self.assertFalse(run.delivered("S-2"))
            self.assertFalse(run.delivered("S-9"))
            self.assertEqual(run.back_to("S-2"), "build")
            self.assertEqual(run.back_to("S-2", "build"), "")
            asks = p.handover("S-2", "build", "# build\n\n## needs-human\n- decision: S-2-01. Which one?\n")
            calm = p.handover("S-2", "tidy", "# tidy\n\n## needs-human\n(none)\n")
            self.assertTrue(run.asks_human(asks))
            self.assertFalse(run.asks_human(calm))
            self.assertEqual(run.verdict_of("S-2"), "")
            self.assertEqual(run.open_decisions("S-2"), "")
            self.assertEqual(run.used_tokens("S-2"), 0)


class RoundTool(unittest.TestCase):
    """A round the build stage sends back (`back: test`) keeps the run's tool: every later stage resolves its own from
    the profile, none inherits the build stage's `tool.build`."""

    def setUp(self):
        for name in ("FACTORY_TOOL_EXPLICIT", "FACTORY_TOOL_CMD"):
            os.environ.pop(name, None)

    def test_a_round_from_a_separate_build_stage_keeps_the_runs_tool(self):
        with project() as p:
            write(os.path.join(p.root, profiles.PROFILE_FILE), "tool.build: codex\n")
            p.story("S-1")
            options = types.SimpleNamespace(max_stages=0, story_budget=0, builder="separate", verifier="separate",
                                            parallel=0)
            run = runner.Run(options, p.root, ".dca-factory/runs", worker="unit:host:1")
            used, sent = [], []

            def run_one(story, tool, stage, dry=False):
                used.append((stage, tool, run.tool_in_flight))
                return 0

            def back_to(story, stage=None):
                if stage == "build" and not sent:
                    sent.append(stage)
                    return "test"
                return "" if stage else "build"
            run.run_one, run.back_to = run_one, back_to
            run.gate = lambda stage, story, gate_path=None: 0
            run.between_stages = lambda story, tool: None
            run.verdict_of = lambda story: "pass"
            run.asks_human = lambda path: False
            run.run_reviews = lambda *args, **kwargs: 0
            run.bump_rounds = lambda story: 1
            self.assertEqual(run.run_stages("S-1", "claude", "plan"), 0)
            self.assertEqual([stage for stage, _t, _u in used],
                             ["plan", "test", "build", "test", "build", "tidy", "judge", "document"])
            self.assertEqual({tool for _s, tool, _u in used}, {"claude"})
            self.assertEqual([unit for stage, _t, unit in used if stage != "build"], ["claude"] * 6)
            self.assertEqual([unit for stage, _t, unit in used if stage == "build"], ["codex", "codex"])


class ToolAndEffortPerUnit(unittest.TestCase):
    """WP-95 items 7 and 8: the tool and the effort a unit runs with, from the profile; `--tool` overrides."""

    def setUp(self):
        for name in ("FACTORY_TOOL_EXPLICIT", "FACTORY_TOOL_CMD", "FACTORY_CLAUDE_ARGS", "FACTORY_CODEX_ARGS"):
            os.environ.pop(name, None)

    tearDown = setUp

    def test_the_unit_names_its_tool_then_the_profile_default_then_the_runs(self):
        with project() as p:
            write(os.path.join(p.root, profiles.PROFILE_FILE),
                  "tool: claude\ntool.verifier: codex\ntool.review: opencode\ntool.review.ddd: codex\n")
            run = a_run(p)
            self.assertEqual(run.tools.tool_for("builder", "claude"), "claude")
            self.assertEqual(run.tools.tool_for("verifier", "claude"), "codex")
            self.assertEqual(run.tools.tool_for("review:ddd", "claude"), "codex")
            self.assertEqual(run.tools.tool_for("review:hexagonal", "claude"), "opencode")
            self.assertEqual(run.tools.tools_of_run("claude"), ["claude", "codex", "opencode"])
            os.environ["FACTORY_TOOL_EXPLICIT"] = "1"
            self.assertEqual(run.tools.tool_for("verifier", "claude"), "claude")

    def test_the_effort_per_unit_is_passed_as_the_tool_takes_it_or_named_as_not_applied(self):
        with project() as p:
            write(os.path.join(p.root, profiles.PROFILE_FILE),
                  "effort.claude: medium\neffort.claude.tidy: low\neffort.opencode: high\n")
            run = a_run(p)
            self.assertEqual(run.tools.effort_choice("claude", "tidy"), ("low", ""))
            self.assertEqual(run.tools.effort_choice("claude", "build"), ("medium", ""))
            self.assertEqual(run.tools.effort_choice("codex", "build"), ("", ""))
            self.assertIn("takes none", run.tools.effort_choice("opencode", "build")[1])
            os.environ["FACTORY_CLAUDE_ARGS"] = "--effort max"
            self.assertIn("overridden", run.tools.effort_choice("claude", "build")[1])
            _env, argv = agents.tool_command(agents.TOOL["claude"], effort="low")
            self.assertEqual(argv[argv.index("--effort") + 1], "low")
            _env, argv = agents.tool_command(agents.TOOL["codex"], effort="high")
            self.assertIn('model_reasoning_effort="high"', argv)


if __name__ == "__main__":
    unittest.main()
