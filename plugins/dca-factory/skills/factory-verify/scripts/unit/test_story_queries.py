"""What a story answers about itself: whether a person released it, its one happy path, the stories a journey
walks — the aggregate's own queries, which the gate's checks phrase."""

import unittest

import support  # noqa: F401 — puts the package on the path
from support import gate_story
from dca_factory.delivery.domain.model.story import ReleaseState, StoryId
from dca_factory.delivery.domain.model.story_words import ScenarioKey

BODY = "## Acceptance criteria\n\n#### a (happy path)\n- Given x\n- When y\n- Then z\n"


class Release(unittest.TestCase):

    def test_no_status_is_unmarked_approved_released_any_other_word_not(self):
        self.assertIs(gate_story("S-1").release_state(), ReleaseState.UNMARKED)
        self.assertIs(gate_story("S-1", front={"status": "approved"}).release_state(), ReleaseState.RELEASED)
        self.assertIs(gate_story("S-1", front={"status": "adopted"}).release_state(), ReleaseState.ADOPTED)
        self.assertIs(gate_story("S-1", front={"status": "delivered"}).release_state(), ReleaseState.DELIVERED)
        for word in ("draft", "superseded", "aproved"):
            self.assertIs(gate_story("S-1", front={"status": word}).release_state(), ReleaseState.UNRELEASED, word)


class HappyPath(unittest.TestCase):

    def test_exactly_one_marked_scenario_is_the_happy_path(self):
        self.assertEqual(gate_story("S-1", body=BODY).happy_path(), ScenarioKey("a"))
        two = BODY + "\n#### b (happy path)\n- Given x\n- When y\n- Then z\n"
        self.assertIsNone(gate_story("S-1", body=two).happy_path())
        self.assertIsNone(gate_story("S-1").happy_path())


class Walks(unittest.TestCase):

    def test_a_journey_walks_its_depends_on_any_other_kind_none(self):
        front = {"kind": "journey", "depends_on": "[S-1, S-2]"}
        self.assertEqual(gate_story("J-1", front=front).walks(), (StoryId("S-1"), StoryId("S-2")))
        self.assertEqual(gate_story("S-3", front={"depends_on": "[S-1]"}).walks(), ())


if __name__ == "__main__":
    unittest.main()
