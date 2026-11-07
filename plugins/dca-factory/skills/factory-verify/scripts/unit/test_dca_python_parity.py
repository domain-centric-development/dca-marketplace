"""The factory keeps its own copy of the Python building blocks and its own architecture checker (it installs
standalone, without PyPI), and both stay readings of DCA-Python: every marker the copy declares exists in
`dca-building-blocks` under the same name, and every rule id the checker reports is one `dca-rules` implements.
Runs where a `dca-python` checkout sits beside the marketplace (or `DCA_PYTHON` names one); skipped elsewhere."""

import ast
import json
import os
import re
import unittest

import support

HERE = os.path.dirname(os.path.abspath(__file__))
DCA_PYTHON = os.environ.get("DCA_PYTHON") or os.path.normpath(os.path.join(HERE, *[".."] * 7, "dca-python"))
BLOCKS = os.path.join(DCA_PYTHON, "dca-building-blocks", "src", "dca_building_blocks", "__init__.py")
RULES = os.path.join(DCA_PYTHON, "dca-rules", "src", "dca_rules", "rules.json")


def declared_classes(path):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef) and not node.name.startswith("_")}


@unittest.skipUnless(os.path.isfile(BLOCKS) and os.path.isfile(RULES), "no dca-python checkout beside the marketplace")
class DcaPythonParityTest(unittest.TestCase):
    def test_every_marker_of_the_copy_exists_in_dca_building_blocks(self):
        with open(BLOCKS, encoding="utf-8") as handle:
            exported = set(re.findall(r'^    "(\w+)",$', handle.read(), re.M))
        own = declared_classes(os.path.join(support.SCRIPTS, "dca_factory", "building_blocks.py"))
        self.assertEqual(set(), own - exported, "markers of the factory's copy that dca-building-blocks lacks")

    def test_every_rule_id_the_checker_reports_is_implemented_in_dca_rules(self):
        with open(os.path.join(HERE, "..", "architecture.py"), encoding="utf-8") as handle:
            reported = set(re.findall(r"DCA-[A-Z]+-\d{3}", handle.read()))
        with open(RULES, encoding="utf-8") as handle:
            implemented = {r["id"] for r in json.load(handle)["rules"] if r.get("implemented")}
        self.assertTrue(reported)
        self.assertEqual(set(), reported - implemented, "ids the factory reports that dca-rules does not implement")


if __name__ == "__main__":
    unittest.main()
