"""What a story is compared against once the main line came into its branch: the base tree as a commit has it,
a file git tracks although the ignore rules name it included, and the tests baseline moved onto the main line."""

import os
import subprocess
import tempfile
import unittest

from support import write
from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from dca_factory import gate
from dca_factory.delivery.adapter.outgoing.files import snapshots


def git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, capture_output=True,
                          text=True, check=True)
    return done.stdout.strip()


def baseline(runs, story):
    path = os.path.join(evidence_dir(runs, story), gate.TESTS_BASELINE)
    with open(path, encoding="utf-8") as handle:
        return dict(reversed(line.split("  ", 1)) for line in handle.read().splitlines() if "  " in line)


class BaseAfterMerge(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.runs = os.path.join(self.root, ".dca-factory", "runs")
        git(self.root, "init", "-q", "-b", "main")
        write(os.path.join(self.root, ".gitignore"), ".vscode/\n.dca-factory/\n")
        write(os.path.join(self.root, ".vscode", "settings.json"), "{}\n")
        for name in ("KeptTest", "ChangedTest", "GoneTest"):
            write(os.path.join(self.root, "src", "test", f"{name}.java"), f"class {name} {{ void a() {{}} }}\n")
        git(self.root, "add", "-A")
        git(self.root, "add", "-f", ".vscode/settings.json")
        git(self.root, "commit", "-qm", "base")

    def tearDown(self):
        self.scratch.cleanup()

    def test_a_tracked_file_the_ignore_rules_name_is_no_change_against_a_commits_tree(self):
        base = git(self.root, "rev-parse", "HEAD^{tree}")
        self.assertEqual(snapshots.tree_changes(self.root, base, snapshots.git_tree(self.root), self.runs), [])
        write(os.path.join(self.root, ".vscode", "settings.json"), '{ "a": 1 }\n')
        self.assertEqual(snapshots.tree_changes(self.root, base, snapshots.git_tree(self.root), self.runs),
                         [("modified", ".vscode/settings.json")])

    def test_the_tests_baseline_moves_onto_the_main_line_and_keeps_the_storys_own_change(self):
        story = "S-1"
        old = git(self.root, "rev-parse", "HEAD^{tree}")
        os.makedirs(evidence_dir(self.runs, story))
        write(os.path.join(self.root, "Untracked_test.py"), "def test_a(): pass\n")
        gate.record_tests_baseline(self.root, self.runs, story)
        before = baseline(self.runs, story)
        self.assertIn("Untracked_test.py", before)
        # the main line changes one test, removes one, adds one
        write(os.path.join(self.root, "src", "test", "ChangedTest.java"), "class ChangedTest { void b() {} }\n")
        os.remove(os.path.join(self.root, "src", "test", "GoneTest.java"))
        write(os.path.join(self.root, "src", "test", "NewTest.java"), "class NewTest { void a() {} }\n")
        git(self.root, "add", "-A", "--", "src")
        git(self.root, "commit", "-qm", "main moves on")
        new = git(self.root, "rev-parse", "HEAD^{tree}")
        # the story weakened KeptTest — on its branch, committed or not: never in the main line's tree
        write(os.path.join(self.root, "src", "test", "KeptTest.java"), "class KeptTest { }\n")
        gate.rebase_tests_baseline(self.root, self.runs, story, new, old)
        after = baseline(self.runs, story)
        self.assertEqual(after["src/test/KeptTest.java"], before["src/test/KeptTest.java"])
        self.assertEqual(after["src/test/ChangedTest.java"], git(self.root, "rev-parse", "HEAD:src/test/ChangedTest.java"))
        self.assertEqual(after["src/test/NewTest.java"], git(self.root, "rev-parse", "HEAD:src/test/NewTest.java"))
        self.assertNotIn("src/test/GoneTest.java", after)
        self.assertEqual(after["Untracked_test.py"], before["Untracked_test.py"])


if __name__ == "__main__":
    unittest.main()
