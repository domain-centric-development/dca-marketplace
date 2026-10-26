"""The judge's confirmed defects a delivery keeps: one row per place and defect, open until closed."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.stage_story import FindingKey, Place
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.service.finding_rules import FindingRules


def key(place, defect):
    return FindingKey(Place(place), Detail(defect))


class Kept(unittest.TestCase):

    def test_a_finding_kept_already_is_not_kept_twice_a_new_one_is(self):
        known = {key("a.py:3", "null")}
        found = [key("a.py:3", "null"), key("a.py:3", "leak"), key("b.py:1", "null")]
        self.assertEqual(FindingRules.kept(known, found), {key("a.py:3", "leak"), key("b.py:1", "null")})


if __name__ == "__main__":
    unittest.main()
