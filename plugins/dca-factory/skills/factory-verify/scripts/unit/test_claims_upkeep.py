"""The story claims' and the project's upkeep commands as use cases, and the stage table as the runner reads it."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.delivery.next_free_story_id import NextFreeStoryIdQuery, NextFreeStoryIdUseCase
from dca_factory.delivery.application.delivery.refresh_claims import RefreshClaimsCommand, RefreshClaimsUseCase
from dca_factory.delivery.application.delivery.release_story_claim import (
    ReleaseStoryClaimCommand, ReleaseStoryClaimUseCase)
from dca_factory.delivery.application.delivery.show_stage_table import ShowStageTableQuery, ShowStageTableUseCase
from dca_factory.delivery.application.upkeep.let_journals_into_git import (
    LetJournalsIntoGitCommand, LetJournalsIntoGitUseCase)
from dca_factory.delivery.domain.model.story import StoryId


class Claims:
    def __init__(self):
        self.calls = []

    def release(self, story, force):
        self.calls.append(("release", story.value, force))
        return 0

    def refresh(self):
        self.calls.append(("refresh",))
        return 0

    def free_id(self, prefix):
        return f"{prefix}-7"


class Upkeep:
    def journals_into_git(self):
        return ".dca-factory/evidence"


class Tables:
    def tool_lines(self):
        return ["TOOL_NAMES=(claude)"]

    def place(self, key):
        return f"product/{key}"


class ClaimsUpkeepTest(unittest.TestCase):

    def test_the_claim_commands_reach_the_remote_through_their_port(self):
        claims = Claims()
        self.assertEqual(0, ReleaseStoryClaimUseCase(claims).execute(ReleaseStoryClaimCommand(StoryId("S-1"), True)))
        self.assertEqual(0, RefreshClaimsUseCase(claims).execute(RefreshClaimsCommand()))
        self.assertEqual("S-7", NextFreeStoryIdUseCase(claims).execute(NextFreeStoryIdQuery("S")))
        self.assertEqual([("release", "S-1", True), ("refresh",)], claims.calls)

    def test_letting_the_journals_into_git_says_where_they_are(self):
        self.assertEqual(".dca-factory/evidence",
                         LetJournalsIntoGitUseCase(Upkeep()).execute(LetJournalsIntoGitCommand()))


class StageTableTest(unittest.TestCase):

    def test_the_table_is_the_domains_pipeline_with_the_tools_and_places_asked_for(self):
        table = ShowStageTableUseCase(Tables()).execute(ShowStageTableQuery(("epics",), with_tools=True))
        self.assertEqual(["plan", "test", "build", "tidy", "judge", "document"], table["order"])
        self.assertEqual(["adopt", "integrate"], table["steps"])
        self.assertEqual({"builder": ["plan", "test", "build", "tidy"], "verifier": ["judge", "document"]},
                         table["windows"])
        self.assertIn(("journey", "test"), table["kinds"])
        self.assertNotIn(("task", "test"), table["kinds"])
        self.assertEqual((["TOOL_NAMES=(claude)"], {"epics": "product/epics"}), (table["tools"], table["places"]))
        self.assertEqual([], ShowStageTableUseCase(Tables()).execute(ShowStageTableQuery())["tools"])


if __name__ == "__main__":
    unittest.main()
