"""What `/factory-run <argument>` means (`RunArgument`, `ResolveRunArgumentUseCase`) and what a refusal cost
(`RefusalKind`, `ShowRefusalsUseCase`)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.run.resolve_run_argument import (
    ResolveRunArgumentQuery, ResolveRunArgumentUseCase)
from dca_factory.delivery.application.shared.gate_refusals import Refused, RefusedBy
from dca_factory.delivery.application.status.show_refusals import ShowRefusalsQuery, ShowRefusalsUseCase
from dca_factory.delivery.domain.model.run_argument import ArgumentMeaning, RunArgument
from dca_factory.delivery.domain.model.story import StoryId
from dca_factory.delivery.domain.model.verdict import CheckName, RefusalKind


class Story:
    def __init__(self, story_id):
        self.id = StoryId(story_id)


class Stories:
    def find_by_id(self, story_id):
        return Story("S-1") if story_id.value.lower() == "s-1" else None

    def ids(self):
        return [StoryId("S-1"), StoryId("S-2")]


class Refusals:
    def stories(self):
        return [StoryId("S-1"), StoryId("S-2")]

    def refused(self, story):
        if story.value == "S-2":
            return []
        return [Refused(RefusedBy.RUNNER, (CheckName("files-listed"),)),
                Refused(RefusedBy.RUNNER, (CheckName("files-listed"), CheckName("tests-red"))),
                Refused(RefusedBy.STAGES, ())]


class RunArgumentTest(unittest.TestCase):

    def test_nothing_is_the_backlog_one_known_word_a_story_one_unknown_word_unknown_more_a_wish(self):
        self.assertIs(ArgumentMeaning.BACKLOG, RunArgument("  ").meaning(None))
        self.assertIs(ArgumentMeaning.STORY, RunArgument("S-1").meaning(StoryId("S-1")))
        self.assertIs(ArgumentMeaning.UNKNOWN, RunArgument("S-9").meaning(None))
        self.assertIs(ArgumentMeaning.WISH, RunArgument("show the newest first").meaning(None))

    def test_resolving_names_the_story_by_its_id_and_an_unknown_word_with_the_backlogs_ids(self):
        resolve = lambda words: ResolveRunArgumentUseCase(Stories()).execute(ResolveRunArgumentQuery(words))
        self.assertEqual(StoryId("S-1"), resolve("s-1").story)
        unknown = resolve("S-9")
        self.assertEqual((ArgumentMeaning.UNKNOWN, "S-9", (StoryId("S-1"), StoryId("S-2"))),
                         (unknown.meaning, unknown.word, unknown.known))
        self.assertIs(ArgumentMeaning.UNKNOWN, resolve("no/id").meaning)


class RefusalsTest(unittest.TestCase):

    def test_a_refusal_is_form_only_when_every_check_it_names_is_about_the_hand_overs_form(self):
        self.assertIs(RefusalKind.FORM, RefusalKind.of((CheckName("files-listed"), CheckName("layout"))))
        self.assertIs(RefusalKind.SUBSTANCE, RefusalKind.of((CheckName("files-listed"), CheckName("tests-red"))))
        self.assertIs(RefusalKind.SUBSTANCE, RefusalKind.of(()))

    def test_the_refusals_are_counted_per_story_the_runners_apart_from_the_stages(self):
        model = ShowRefusalsUseCase(Refusals()).execute(ShowRefusalsQuery())
        self.assertEqual({"runner": {"form": 1, "substance": 1, "checks": {"files-listed": 2, "tests-red": 1}},
                          "stages": {"form": 0, "substance": 1, "checks": {"unnamed": 1}}}, model["stories"]["S-1"])
        self.assertEqual({}, model["stories"]["S-2"])
        self.assertEqual(["S-2"], list(ShowRefusalsUseCase(Refusals()).execute(ShowRefusalsQuery("S-2"))["stories"]))


if __name__ == "__main__":
    unittest.main()
