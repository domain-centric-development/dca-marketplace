"""Test strength as a measure: the profile's `mutation:` over a story's changed production files after its judge, the
score its output states, the status's reading of it — informational, never a gate — and setup's proposal."""

import os
import tempfile
import unittest

from support import write
from dca_factory.delivery.adapter.outgoing.files.status_facts import mutation_of
from dca_factory.delivery.adapter.outgoing.install.presets import Detection
from dca_factory.delivery.adapter.outgoing.stack.mutation_runs import (
    classes_of, mutation_command, run_mutation, score_of)

PRESETS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "factory-run",
                                        "templates", "presets"))


class MutationTest(unittest.TestCase):

    def test_the_changed_classes_by_their_qualified_names_and_the_files_as_they_are(self):
        files = ["src/main/java/com/example/a/Thing.java", "src/main/kotlin/com/example/b/Other.kt", "app/thing.py"]
        self.assertEqual(classes_of(files), ["com.example.a.Thing", "com.example.b.Other"])
        self.assertEqual(mutation_command("./gradlew pitest -PtargetClasses={classes}", files),
                         "./gradlew pitest -PtargetClasses=com.example.a.Thing,com.example.b.Other")
        self.assertEqual(mutation_command("tool {files}", files[2:]), "tool app/thing.py")

    def test_the_score_as_pit_and_stryker_state_it(self):
        self.assertEqual(score_of(">> Generated 22 mutations Killed 18 (82%)\n"), "82")
        self.assertEqual(score_of("The final mutation score is 72.73 %\n"), "72.73")
        self.assertIsNone(score_of("BUILD SUCCESSFUL\n"))

    def test_a_run_says_its_exit_and_output(self):
        with tempfile.TemporaryDirectory() as folder:
            code, output = run_mutation("echo 'Killed 3 (75%)'; exit 2", folder, 30)
        self.assertEqual((code, score_of(output)), (2, "75"))

    def test_the_status_reads_the_last_measure(self):
        self.assertIsNone(mutation_of([]))
        event = lambda **fields: dict(kind="mutation", name="-", fields=fields)
        self.assertEqual(mutation_of([event(skipped="no-key")]), "skipped")
        self.assertEqual(mutation_of([event(skipped="no-key"), event(exit="0", score="82")]), "82")
        self.assertEqual(mutation_of([event(exit="1")]), "no score")

    def test_setup_proposes_pit_where_the_build_applies_it(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, "build.gradle"), "plugins { id 'info.solidsoft.pitest' version '1.15.0' }\n")
            write(os.path.join(root, "gradlew"), "#!/bin/sh\n")
            try:
                os.chdir(root)
                values, _applied, _governance = Detection(PRESETS, "python3", "", ()).detect()
            finally:
                os.chdir(cwd)
        self.assertEqual(values.get("mutation"), "./gradlew pitest -PtargetClasses={classes}")


if __name__ == "__main__":
    unittest.main()
