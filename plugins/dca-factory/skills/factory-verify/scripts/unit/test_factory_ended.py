"""A factory that ended on its own says which story stopped it, so the status can drop the word once that story is
delivered."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.outgoing.process.factory_process import stopped_story


class FactoryEndedTest(unittest.TestCase):

    def test_the_last_word_names_the_story_that_stopped_it(self):
        self.assertEqual("the-order-changed", stopped_story(
            "story the-order-changed stopped (exit 1) — the backlog run ends here."))

    def test_a_word_without_a_stopped_story_names_none(self):
        self.assertEqual("", stopped_story("no word in its log"))
        self.assertEqual("", stopped_story("Traceback (most recent call last): the story file is broken"))


if __name__ == "__main__":
    unittest.main()
