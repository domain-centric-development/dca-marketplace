"""A story's kind (`KindWord`), the skeletons a stage starts from, and a tool's probe — as the cli asks them."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.delivery.probe_tool import Probed, ProbeToolQuery, ProbeToolUseCase
from dca_factory.delivery.application.delivery.write_skeleton import Skeleton, WriteSkeletonCommand, WriteSkeletonUseCase
from dca_factory.delivery.application.shared.tool_binaries import Probe
from dca_factory.delivery.domain.model.stage import StoryKind
from dca_factory.delivery.domain.model.story import KindWord, StoryStatus


class Skeletons:
    def __init__(self):
        self.calls = []

    def plan(self, story):
        self.calls.append(("plan", story))
        return 0

    def files(self, story, stage):
        self.calls.append(("files", story, stage))
        return 0

    def document(self, story):
        self.calls.append(("document", story))
        return 1


class Tools:
    def names(self):
        return ["claude", "codex"]

    def binary(self, tool):
        return tool

    def probe(self, tool):
        return Probe("claude", ("--add-dir",), ()) if tool == "claude" else None


class KindTest(unittest.TestCase):

    def test_a_named_journey_or_task_is_that_an_adopted_status_an_adoption_else_a_story(self):
        self.assertIs(StoryKind.JOURNEY, KindWord(" Journey ").kind(StoryStatus.APPROVED))
        self.assertIs(StoryKind.TASK, KindWord("task").kind(StoryStatus.ADOPTED))
        self.assertIs(StoryKind.ADOPT, KindWord("").kind(StoryStatus.ADOPTED))
        self.assertIs(StoryKind.STORY, KindWord("feature").kind(StoryStatus.DRAFT))


class SkeletonTest(unittest.TestCase):

    def test_each_skeleton_is_written_by_its_writer_and_answers_with_its_exit(self):
        skeletons = Skeletons()
        write = WriteSkeletonUseCase(skeletons)
        self.assertEqual(0, write.execute(WriteSkeletonCommand(Skeleton.PLAN, "S-1")))
        self.assertEqual(0, write.execute(WriteSkeletonCommand(Skeleton.FILES, "S-1", "build")))
        self.assertEqual(1, write.execute(WriteSkeletonCommand(Skeleton.DOCUMENT, "S-1")))
        self.assertEqual([("plan", "S-1"), ("files", "S-1", "build"), ("document", "S-1")], skeletons.calls)


class ProbeTest(unittest.TestCase):

    def test_an_unknown_tool_names_the_known_a_missing_binary_is_not_probed(self):
        probe = lambda tool: ProbeToolUseCase(Tools()).execute(ProbeToolQuery(tool))
        self.assertEqual((Probed.UNKNOWN, ("claude", "codex")), (probe("x").outcome, probe("x").known))
        self.assertIs(Probed.NOT_INSTALLED, probe("codex").outcome)
        self.assertEqual(("--add-dir",), probe("claude").found.required)


if __name__ == "__main__":
    unittest.main()
