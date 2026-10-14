"""#153: a blob is read as git holds it — the gate's git helper strips its answers, and a test file whose first line
is indented read through it would be a changed test."""

import os
import subprocess
import tempfile
import unittest

from support import state, write
from dca_factory import contract, gate

TEST = "src/test/java/com/example/ShopTest.java"
INDENTED = "    package com.example;\nclass ShopTest {\n  @Test void opens() { assertTrue(shop.open()); }\n}\n"


class GitBlob(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.runs = os.path.join(self.root, ".dca-factory", "runs")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        write(os.path.join(self.root, ".gitignore"), ".dca-factory/\n")
        write(os.path.join(self.root, TEST), INDENTED)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], cwd=self.root,
                       check=True)

    def tearDown(self):
        self.scratch.cleanup()

    def test_a_blob_keeps_its_first_lines_indentation_and_its_last_newline(self):
        self.assertEqual(contract.git_blob(self.root, f"HEAD:{TEST}"), (0, INDENTED))

    def test_a_blob_that_does_not_exist_answers_with_a_code(self):
        self.assertNotEqual(contract.git_blob(self.root, "HEAD:nothing.txt")[0], 0)

    def test_a_test_whose_first_line_is_indented_and_unchanged_is_kept(self):
        gate.record_tests_baseline(self.root, self.runs, "STORY-1")
        result = gate.Result()
        gate.check_existing_tests(result, self.root, self.runs, "STORY-1")
        self.assertEqual([(verdict, check) for verdict, check, _m in result.entries], [("pass", "tests-kept")])
        self.assertNotIn("arranged", result.entries[0][2])


if __name__ == "__main__":
    unittest.main()
