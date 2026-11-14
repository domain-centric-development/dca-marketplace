"""The reviewers' findings as rows: one line per finding, derived from the review files, the files untouched."""

import os
import shutil
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.outgoing.files.review_rows import rows_of, write_review_rows

REVIEW = """# Domain Review

**Scope:** 3 files

## Findings

### must-fix (0)

None.

### should-fix (1)

- **src/main/java/app/Title.java:6 (diff L478)**: the value object's invariant can be bypassed. It goes on.
  *Why:* a long argument the judge reads only where the row is not enough.
  *Fix:* add a compact constructor that refuses blank values. Then more.

### nits (2)

- **src/main/resources/schema.sql:8** — Missing "why" comment: the ALTER reads as a duplicate. Fix: add a comment.
- **src/test/java/app/TitleTest.java:14** — Two asserts in one test

## Strengths

- **Ports point inward.** Not a finding.
"""


class ReviewRowsTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def test_a_finding_is_its_rank_its_place_its_claim_and_its_fix_and_no_argument(self):
        rows = rows_of(REVIEW)
        self.assertEqual(["should-fix", "nit", "nit"], [r[0] for r in rows])
        self.assertEqual("src/main/java/app/Title.java:6 (diff L478)", rows[0][1])
        self.assertEqual("the value object's invariant can be bypassed. "
                         "Fix: add a compact constructor that refuses blank values.", rows[0][2])
        self.assertNotIn("long argument", rows[0][2])
        self.assertIn("Fix: add a comment.", rows[1][2])
        self.assertEqual("Two asserts in one test", rows[2][2])

    def test_strengths_and_an_empty_rank_are_no_rows(self):
        self.assertEqual([], rows_of("## Findings\n\n### must-fix (0)\n\nNone.\n\n## Strengths\n\n- **x** good\n"))

    def test_the_rows_file_counts_per_perspective_and_names_what_has_no_file(self):
        with open(os.path.join(self.folder, "ddd.md"), "w", encoding="utf-8") as handle:
            handle.write(REVIEW)
        before = open(os.path.join(self.folder, "ddd.md"), encoding="utf-8").read()
        path = write_review_rows(self.folder, ["ddd", "hexagonal"])
        text = open(path, encoding="utf-8").read()
        self.assertIn("- ddd: 0 must-fix, 1 should-fix, 2 nit", text)
        self.assertIn("- hexagonal: no file", text)
        self.assertIn("- ddd · should-fix · src/main/java/app/Title.java:6 (diff L478) — the value object", text)
        self.assertEqual(before, open(os.path.join(self.folder, "ddd.md"), encoding="utf-8").read())

    def test_no_review_file_writes_no_rows(self):
        self.assertIsNone(write_review_rows(self.folder, ["ddd"]))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "findings.md")))


if __name__ == "__main__":
    unittest.main()
