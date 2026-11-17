"""The findings from before contract 39 classified once (WP-223): the rows without a class are counted, and what a
classify-findings request wrote is held to the empty class cells and the `classes:` mark."""

import os
import subprocess
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.outgoing.files.finding_class_files import FindingClassFiles, class_problems
from dca_factory.delivery.application.shared.requests import KIND

OLD = ("---\nstory: S-1\n---\n\n# Findings — S-1\n\n"
       "| # | Perspective | File:line | Severity | Origin | Outcome | In plain words | Defect | Fix | Status |\n"
       "|---|---|---|---|---|---|---|---|---|---|\n"
       "| 1 | clean-code | src/A.java:3 | minor | introduced |  | a helper copied | duplicate fixture | lift it | open |\n"
       "| 2 | ddd | src/B.java:9 | minor | introduced |  | a word drifts | domain-term: `Item` | rename | open |\n")
HEAD = ("| # | Perspective | File:line | Severity | Origin | Outcome | In plain words | Defect | Fix | Status | Target "
        "| Type | Qualifier |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def classified(first=("test", "duplication", "extraneous"), second=("—", "—", "—"), defect="duplicate fixture",
               mark=True):
    top = "---\nstory: S-1\n" + ("classes: backfilled 2026-11-17 by request R-1 (2 rows, 1 without a fitting value)\n"
                                  if mark else "") + "---\n\n# Findings — S-1\n\n"
    return (top + HEAD
            + f"| 1 | clean-code | src/A.java:3 | minor | introduced |  | a helper copied | {defect} | lift it | open "
              f"| {' | '.join(first)} |\n"
            + f"| 2 | ddd | src/B.java:9 | minor | introduced |  | a word drifts | domain-term: `Item` | rename | open "
              f"| {' | '.join(second)} |\n")


class ClassFillTest(unittest.TestCase):

    def test_only_empty_class_cells_from_the_lists_and_the_mark_may_change(self):
        self.assertEqual([], class_problems(OLD, classified()))
        self.assertEqual([], class_problems(OLD, classified(mark=False)))
        self.assertIn("row 1", class_problems(OLD, classified(defect="copied helper"))[0])           # another cell
        self.assertIn("row 1", class_problems(OLD, classified(first=("tests", "copy", "extra")))[0])  # outside lists
        self.assertIn("row 2", class_problems(OLD, classified(second=("—", "naming", "—")))[0])       # `—` in all three
        dropped = classified().replace("| 2 | ddd", "| 3 | ddd").split("\n")
        self.assertTrue(class_problems(OLD, "\n".join(dropped[:-2]) + "\n"))                         # a row removed

    def test_a_classed_row_is_left_as_it_is(self):
        once = classified()
        self.assertTrue(class_problems(once, classified(first=("code", "duplication", "extraneous"))))

    def test_the_rows_without_a_class_are_counted_and_a_request_holds_to_the_cells(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "product", "epics", "e-1", "S-1")
            os.makedirs(folder)
            with open(os.path.join(folder, "story.md"), "w", encoding="utf-8") as out:
                out.write("---\nid: S-1\nepic: e-1\nstatus: delivered\n---\n\n# S-1\n")
            path = os.path.join(folder, "findings.md")
            with open(path, "w", encoding="utf-8") as out:
                out.write(OLD)
            for command in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
                subprocess.run(["git", *command], cwd=root, check=True)
            cwd = os.getcwd()
            os.chdir(root)
            try:
                files = FindingClassFiles(root)
                self.assertEqual(2, files.count().value)
                relative = "product/epics/e-1/S-1/findings.md"
                with open(path, "w", encoding="utf-8") as out:
                    out.write(classified())
                self.assertIsNone(files.refused([relative]))
                self.assertEqual(1, files.count().value)          # the `—` row stays without a listed class
                with open(path, "w", encoding="utf-8") as out:
                    out.write(classified(defect="rewritten"))
                self.assertIsNotNone(files.refused([relative]))
                files.restore([relative])
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(OLD, handle.read())
                self.assertIsNotNone(files.refused(["product/overview.md"]))
            finally:
                os.chdir(cwd)

    def test_the_request_kind_runs_the_decisions_skill_and_names_nothing(self):
        kind = KIND["classify-findings"]
        self.assertEqual(("factory-decisions", (), "none"), (kind.skill, kind.keys, kind.words))


if __name__ == "__main__":
    unittest.main()
