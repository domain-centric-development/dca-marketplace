"""The runner sends a story whose mapped test changed after it was seen red back to its test stage — except a tidy
that runs again: it moved the test itself, and its gate re-proves it on the red tree (WP-151 A)."""

import os
import unittest

from support import project, write
from dca_factory import gate
from dca_factory.delivery.adapter.outgoing.files import journal_files as journal
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles
from dca_factory.delivery.adapter.outgoing.files import story_layout as layout
from dca_factory.delivery.adapter.outgoing.files import kept_files

TESTS = """# Tests

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-the-thing | com.example.WidgetPageTest#showsTheThing |
"""

PAGE_TEST = os.path.join("src", "test", "java", "com", "example", "WidgetPageTest.java")


class RedTree(unittest.TestCase):

    def setup(self, p, red_tree=True, ended=("build",)):
        profiles.set_places({})
        p.story("S-1")
        p.run_file("S-1", "tests.md", TESTS)
        test_file = write(os.path.join(p.root, PAGE_TEST), "class WidgetPageTest { void showsTheThing() {} }\n")
        p.evidence("S-1", ".tests-red", f"com.example.WidgetPageTest#showsTheThing\t{layout.file_digest(test_file)}\n")
        if red_tree:
            p.evidence("S-1", kept_files.RED_TREE, "4b825dc642cb6eb9a060e54bf8d69288fbee4904\n")
        for stage in ended:
            journal.journal_append(p.runs, "S-1", "stage-start", stage)
            journal.journal_append(p.runs, "S-1", "stage-end", stage, "exit=0")
        write(test_file, "class WidgetPageTest { void showsTheThing() { page.thing(); } }\n")

    def test_a_tidy_that_runs_again_keeps_its_moved_test(self):
        with project() as p:
            self.setup(p, ended=("build", "tidy"))
            self.assertEqual(kept_files.stale_red_proof(p.root, p.runs, "S-1", "tidy"), [])

    def test_a_tidy_after_the_build_goes_to_the_test_stage(self):
        with project() as p:
            self.setup(p, ended=("build",))
            self.assertEqual(len(kept_files.stale_red_proof(p.root, p.runs, "S-1", "tidy")), 1)

    def test_without_a_red_tree_the_tidy_goes_to_the_test_stage(self):
        with project() as p:
            self.setup(p, red_tree=False, ended=("build", "tidy"))
            self.assertEqual(len(kept_files.stale_red_proof(p.root, p.runs, "S-1", "tidy")), 1)

    def test_the_build_goes_to_the_test_stage(self):
        with project() as p:
            self.setup(p, ended=("build", "tidy"))
            self.assertEqual(len(kept_files.stale_red_proof(p.root, p.runs, "S-1", "build")), 1)

    def test_a_test_path_is_a_test_file_or_below_a_test_folder(self):
        for path, expected in (("src/test/java/a/Page.java", True), ("Shop.Tests/Support/Page.cs", True),
                               ("e2e/widget.spec.ts", True), ("src/main/java/a/Latest.java", False),
                               ("src/integrationTest/java/a/Support.java", True)):
            self.assertEqual(kept_files.is_test_path(path), expected, path)


if __name__ == "__main__":
    unittest.main()
