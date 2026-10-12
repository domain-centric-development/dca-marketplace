"""The runner's record of its green suite runs (WP-79 A3) belongs to the tree it was made on: a break's scratch copy,
run through the same invocation, is run — never answered from the record of the tree it was copied from."""

import os
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401 — puts the package on the path
from dca_factory import gate


class SuitesRecordTest(unittest.TestCase):

    def record_for(self, tree):
        return {"path": os.path.join(tree, "suites.tsv"), "key": "fixture-key", "tree": "digest",
                "rows": {"false": ("2026-10-12T20:00:00Z", 0, [])}, "cwd": os.path.realpath(tree)}

    def test_the_tree_the_record_was_made_on_reads_it(self):
        with tempfile.TemporaryDirectory() as tree:
            with mock.patch.object(gate, "SUITES_RECORD", self.record_for(tree)):
                code, _output, _ran, reused = gate.recorded_run("false", tree)
        self.assertEqual(0, code)
        self.assertIn("recorded at", reused)

    def test_a_scratch_copy_runs_the_invocation_itself(self):
        with tempfile.TemporaryDirectory() as tree, tempfile.TemporaryDirectory() as copy:
            with mock.patch.object(gate, "SUITES_RECORD", self.record_for(tree)):
                code, _output, _ran, reused = gate.recorded_run("false", copy)
        self.assertNotEqual(0, code)
        self.assertEqual("", reused)


if __name__ == "__main__":
    unittest.main()
