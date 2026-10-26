"""The claims of several factories on one backlog (WP-93): who meets whom, what a fetch does to a claim, who may
release it, which id is free."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.claim import ClaimedFor, ClaimTitle, Fate, IdPrefix, Meeting, Worker
from dca_factory.delivery.domain.model.epic import EpicId
from dca_factory.delivery.domain.model.stage_story import Presence
from dca_factory.delivery.domain.model.story import StoryId, StoryStatus
from dca_factory.delivery.domain.service.claim_rules import ClaimRules

ME, YOU = Worker("me (a)"), Worker("you (b)")
STORY = ClaimedFor(EpicId("shop"), ClaimTitle("Pay"))


class Claims(unittest.TestCase):

    def test_an_own_claim_holds_another_story_under_the_id_collides_else_another_factory_runs_it(self):
        self.assertIs(ClaimRules.meets(ME, ME, ClaimedFor(EpicId("x"), ClaimTitle("y")), STORY), Meeting.OWN)
        self.assertIs(ClaimRules.meets(YOU, ME, ClaimedFor(EpicId("shop"), ClaimTitle("Ship")), STORY),
                      Meeting.COLLISION)
        self.assertIs(ClaimRules.meets(YOU, ME, ClaimedFor(EpicId(""), ClaimTitle("")), STORY), Meeting.OTHERS)

    def test_delivered_on_the_main_line_releases_missing_without_a_trace_orphans(self):
        absent, present = Presence.ABSENT, Presence.PRESENT
        self.assertIs(ClaimRules.fate(StoryStatus.DELIVERED, absent, absent), Fate.RELEASED)
        self.assertIs(ClaimRules.fate(None, absent, absent), Fate.ORPHAN)
        self.assertIs(ClaimRules.fate(None, present, absent), Fate.HOLDS)
        self.assertIs(ClaimRules.fate(None, absent, present), Fate.HOLDS)
        self.assertIs(ClaimRules.fate(StoryStatus.APPROVED, absent, absent), Fate.HOLDS)

    def test_only_an_own_claim_is_released_without_force(self):
        self.assertIs(ClaimRules.releases(YOU, ME, Presence.ABSENT), Presence.ABSENT)
        self.assertIs(ClaimRules.releases(YOU, ME, Presence.PRESENT), Presence.PRESENT)
        self.assertIs(ClaimRules.releases(ME, ME, Presence.ABSENT), Presence.PRESENT)

    def test_the_next_id_follows_the_highest_and_keeps_its_width(self):
        used = {StoryId("STORY-007"), StoryId("STORY-12"), StoryId("OTHER-99")}
        self.assertEqual(ClaimRules.next_id(IdPrefix("STORY"), used), StoryId("STORY-013"))
        self.assertEqual(ClaimRules.next_id(IdPrefix("STORY"), set()), StoryId("STORY-01"))


if __name__ == "__main__":
    unittest.main()
