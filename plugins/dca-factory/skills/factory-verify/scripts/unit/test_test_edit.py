"""What a story did to a test that existed before it."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.test_facts import TestDiff, TestEdit

YES, NO = True, False


class Edit(unittest.TestCase):

    def test_switched_off_outweighs_kept_lines(self):
        self.assertIs(TestDiff(YES, YES, YES).edit(), TestEdit.SWITCHED_OFF)

    def test_lines_kept_then_assertions_kept_then_changed(self):
        self.assertIs(TestDiff(NO, YES, NO).edit(), TestEdit.KEPT)
        self.assertIs(TestDiff(NO, NO, YES).edit(), TestEdit.ARRANGED)
        self.assertIs(TestDiff(NO, NO, NO).edit(), TestEdit.CHANGED)


if __name__ == "__main__":
    unittest.main()
