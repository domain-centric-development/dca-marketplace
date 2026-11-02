"""A discovery report read as a person reads it: each section with what it says."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.discovery.adapter.outgoing.files.report_files import ReportFiles
from dca_factory.discovery.domain.model.report import Topic


class ReportSectionsTest(unittest.TestCase):

    def test_a_report_reads_section_by_section(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "product", "discovery", "t"))
            with open(os.path.join(root, "product", "discovery", "t", "discovery.md"), "w", encoding="utf-8") as handle:
                handle.write("# T\n\n## Problem\nReaders type every book again. [S1]\n\n## Sources\n- S1: the form\n")
            files = ReportFiles(root, "product/discovery")
            self.assertEqual([("Problem", "Readers type every book again. [S1]"), ("Sources", "- S1: the form")],
                             files.sections(Topic("t")))
            self.assertEqual([], files.sections(Topic("none")))


if __name__ == "__main__":
    unittest.main()
