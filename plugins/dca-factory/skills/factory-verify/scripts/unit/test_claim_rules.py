"""The claims of several factories on one backlog (WP-93): who meets whom, what a fetch does to a claim, who may
release it, which id is free."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.claim import Claim, ClaimedFor, ClaimTitle, ClaimTrace, Fate, IdPrefix, Meeting, Worker
from dca_factory.delivery.domain.model.epic import EpicId
from dca_factory.delivery.domain.model.stage_story import Presence
from dca_factory.delivery.domain.model.story import StoryId, StoryStatus

ME, YOU = Worker("me (a)"), Worker("you (b)")
STORY = ClaimedFor(EpicId("shop"), ClaimTitle("Pay"))


class Claims(unittest.TestCase):

    def test_an_own_claim_holds_another_story_under_the_id_collides_else_another_factory_runs_it(self):
        self.assertIs(Claim(ME, ClaimedFor(EpicId("x"), ClaimTitle("y"))).meets(ME, STORY), Meeting.OWN)
        self.assertIs(Claim(YOU, ClaimedFor(EpicId("shop"), ClaimTitle("Ship"))).meets(ME, STORY),
                      Meeting.COLLISION)
        self.assertIs(Claim(YOU, ClaimedFor(EpicId(""), ClaimTitle(""))).meets(ME, STORY), Meeting.OTHERS)

    def test_delivered_on_the_main_line_releases_missing_without_a_trace_orphans(self):
        absent, present = Presence.ABSENT, Presence.PRESENT
        self.assertIs(ClaimTrace(StoryStatus.DELIVERED, absent, absent).fate(), Fate.RELEASED)
        self.assertIs(ClaimTrace(None, absent, absent).fate(), Fate.ORPHAN)
        self.assertIs(ClaimTrace(None, present, absent).fate(), Fate.HOLDS)
        self.assertIs(ClaimTrace(None, absent, present).fate(), Fate.HOLDS)
        self.assertIs(ClaimTrace(StoryStatus.APPROVED, absent, absent).fate(), Fate.HOLDS)

    def test_only_an_own_claim_is_released_without_force(self):
        self.assertIs(Claim(YOU, STORY).released_by(ME, Presence.ABSENT), Presence.ABSENT)
        self.assertIs(Claim(YOU, STORY).released_by(ME, Presence.PRESENT), Presence.PRESENT)
        self.assertIs(Claim(ME, STORY).released_by(ME, Presence.ABSENT), Presence.PRESENT)

    def test_the_next_id_follows_the_highest_and_keeps_its_width(self):
        used = {StoryId("STORY-007"), StoryId("STORY-12"), StoryId("OTHER-99")}
        self.assertEqual(IdPrefix("STORY").next_id(used), StoryId("STORY-013"))
        self.assertEqual(IdPrefix("STORY").next_id(set()), StoryId("STORY-01"))


if __name__ == "__main__":
    unittest.main()
