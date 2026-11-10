"""What judges a stage is out of its reach: the guarded set — the profile and the `guarded:` globs —, the paths the
runner walls off for a stage, the announced ones opened, and the setup's proposal of `guarded:`."""

import os
import tempfile
import unittest

from support import write
from dca_factory.delivery.adapter.outgoing.install.presets import Detection
from dca_factory.delivery.adapter.outgoing.tools.agents import TOOL, tool_command
from dca_factory.delivery.domain.model.guarded import GuardedChange, GuardedPattern, GuardedSet
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.model.story_words import Place

SET = GuardedSet.of(Place("dca-factory.profile.yaml"), Detail("src/test-architecture/** .githooks/**"))
RULES = Place("src/test-architecture/resources/dca-archunit.properties")


class GuardedSetTest(unittest.TestCase):

    def test_the_profile_is_guarded_without_a_key(self):
        alone = GuardedSet.of(Place("dca-factory.profile.yaml"), Detail(""))
        self.assertTrue(alone.covers(Place("dca-factory.profile.yaml")))
        self.assertFalse(alone.covers(Place("src/main/App.java")))

    def test_a_glob_covers_what_lies_below_it_and_nothing_beside_it(self):
        self.assertTrue(SET.covers(RULES))
        self.assertTrue(SET.covers(Place(".githooks/pre-commit")))
        self.assertFalse(SET.covers(Place("src/test/java/AppTest.java")))
        self.assertTrue(GuardedPattern("**/dca-archunit.properties").covers(RULES))
        self.assertTrue(GuardedPattern("src/test-architecture").covers(RULES))

    def test_nothing_announced_walls_every_glob(self):
        self.assertEqual(SET.walled((), ()), SET.patterns)

    def test_an_announced_path_opens_exactly_itself(self):
        announced = (GuardedChange(RULES, Detail("the scaffold entry goes")),)
        other = Place("src/test-architecture/java/ArchitectureTest.java")
        walls = SET.walled(announced, (RULES, other))
        self.assertIn(GuardedPattern(other.value), walls)
        self.assertNotIn(GuardedPattern(RULES.value), walls)
        self.assertNotIn(GuardedPattern("src/test-architecture/**"), walls)
        self.assertIn(GuardedPattern(".githooks/**"), walls)
        self.assertIn(GuardedPattern("dca-factory.profile.yaml"), walls)


class WallTest(unittest.TestCase):

    def test_claude_is_denied_every_edit_of_a_guarded_path(self):
        _env, argv = tool_command(TOOL["claude"], guarded=["/w/src/test-architecture/**", "/h/dca-factory.profile.yaml"])
        denied = argv[argv.index("--disallowedTools") + 1]
        self.assertIn("Edit(//w/src/test-architecture/**)", denied)
        self.assertIn("Edit(//h/dca-factory.profile.yaml)", denied)


class ProposalTest(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.scratch.cleanup()

    def proposal(self):
        os.chdir(self.root)
        return Detection(os.path.join(self.root, "presets"), "python3", "", ()).guarded()

    def test_setup_proposes_the_hook_the_rule_selection_and_the_suite(self):
        write(os.path.join(self.root, ".githooks", "pre-commit"), "#!/bin/sh\n")
        write(os.path.join(self.root, "src", "test-architecture", "resources", "dca-archunit.properties"), "x = y\n")
        write(os.path.join(self.root, "src", "test-architecture", "java", "com", "example", "app",
                           "ArchitectureTest.java"), "class ArchitectureTest extends DcaArchitectureTest {}\n")
        proposed = self.proposal().split()
        self.assertEqual(proposed, [".githooks/**", "src/test-architecture/resources/dca-archunit.properties",
                                    "src/test-architecture/java/com/example/app/ArchitectureTest.java"])

    def test_a_project_without_them_gets_nothing_proposed(self):
        write(os.path.join(self.root, "src", "main", "App.java"), "class App {}\n")
        self.assertEqual(self.proposal(), "")


if __name__ == "__main__":
    unittest.main()
