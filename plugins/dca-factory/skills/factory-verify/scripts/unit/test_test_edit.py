"""What a story did to a test that existed before it."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.stage_story import Presence, TestEdit

YES, NO = Presence.PRESENT, Presence.ABSENT


class Edit(unittest.TestCase):

    def test_switched_off_outweighs_kept_lines(self):
        self.assertIs(TestEdit.of(YES, YES, YES), TestEdit.SWITCHED_OFF)

    def test_lines_kept_then_assertions_kept_then_changed(self):
        self.assertIs(TestEdit.of(NO, YES, NO), TestEdit.KEPT)
        self.assertIs(TestEdit.of(NO, NO, YES), TestEdit.ARRANGED)
        self.assertIs(TestEdit.of(NO, NO, NO), TestEdit.CHANGED)


if __name__ == "__main__":
    unittest.main()
