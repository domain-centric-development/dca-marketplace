"""What the runner reads in its own process: the profile and the places as a cli started where it stands would."""

import os
import tempfile
import types
import unittest

from support import contract, project, state, write
from dca_factory import runner


def a_run(p):
    options = types.SimpleNamespace(max_stages=0, story_budget=0, builder="shared", verifier="shared", parallel=0)
    return runner.Run(options, p.root, ".dca-factory/runs", worker="unit:host:1")


class Readers(unittest.TestCase):

    def tearDown(self):
        os.environ.pop("FACTORY_HOME", None)

    def test_the_profile_is_read_on_every_question(self):
        with project() as p:
            profile = write(os.path.join(p.root, contract.PROFILE_FILE), "model.claude: sonnet\n")
            run = a_run(p)
            self.assertEqual(run.model_key("claude", "build"), "sonnet")
            write(profile, "model.claude: sonnet\nmodel.claude.build: opus\n")
            self.assertEqual(run.model_key("claude", "build:2"), "opus")
            self.assertEqual(run.model_key("codex", "build"), "")

    def test_in_a_worktree_the_places_are_the_main_checkouts_and_back_home_they_are_relative_again(self):
        with project() as p, tempfile.TemporaryDirectory() as tree:
            write(os.path.join(p.root, contract.PROFILE_FILE), "carrier.guard: the-guard\n")
            p.run_file("S-1", "judge.md", "## Verdict\nverdict: `approved`\n")
            run = a_run(p)
            os.chdir(tree)
            os.environ["FACTORY_HOME"] = p.root
            self.assertIn("the-guard", run.guard_sentence())
            self.assertEqual(contract.place("runs"), f"{p.root}/.dca-factory/runs")
            self.assertEqual(run.verdict_of("S-1"), "approved")
            run.journal_line("S-1", "2026-10-10T10:00:00Z\tnote\t-\twhy=from-the-tree")
            self.assertEqual([e["kind"] for e in state.journal_events(p.runs, "S-1")], ["note"])
            os.chdir(p.root)
            os.environ.pop("FACTORY_HOME")
            run.profile()
            self.assertEqual(contract.place("runs"), ".dca-factory/runs")

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


if __name__ == "__main__":
    unittest.main()
