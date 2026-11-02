"""One part of the project description, read as written: each section with what it says, guidance left out."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.outgoing.files.description_files import DescriptionFiles
from dca_factory.delivery.application.description.show_part import ShowPartQuery, ShowPartUseCase
from dca_factory.sharedkernel.application.profile import Profile


class DescriptionPartTest(unittest.TestCase):

    def test_a_part_reads_section_by_section_without_its_guidance(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "product"))
            with open(os.path.join(root, "product", "overview.md"), "w", encoding="utf-8") as handle:
                handle.write("# Shop\n\n## What and for whom\n\n<!-- who uses it -->\nA shop for **shoppers**.\n\n"
                             "## Surfaces\n\n<!-- the pages -->\n")
            view = ShowPartUseCase(DescriptionFiles(root, Profile({}))).execute(ShowPartQuery("product"))
            self.assertEqual(("product/overview.md", True), (view["path"], view["present"]))
            self.assertEqual([("What and for whom", "A shop for **shoppers**."), ("Surfaces", "")],
                             [(s["heading"], s["text"]) for s in view["sections"]])

    def test_a_missing_part_has_no_sections(self):
        with tempfile.TemporaryDirectory() as root:
            view = ShowPartUseCase(DescriptionFiles(root, Profile({}))).execute(ShowPartQuery("tech"))
            self.assertEqual((False, []), (view["present"], view["sections"]))


if __name__ == "__main__":
    unittest.main()
