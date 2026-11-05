"""The pictures a stage took of what it built (WP-184): read from the story's run folder, newest first, each with the
stage that took it — a file that is no picture, or a link out of the folder, is left out."""

import os
import shutil
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
import sys
import time
from dca_factory.delivery.adapter.outgoing.files.run_shots import collect_shots, shots_of
from dca_factory.delivery.adapter.outgoing.stack.suite_runs import SuiteOwner, suite_run
from dca_factory.delivery.domain.model.shot import Instant

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


#: The interpreter as a profile command names it: a profile command runs through bash on Windows too, which would
#: take the backslashes of `C:\…\python.exe` for escapes.
PYTHON = sys.executable.replace("\\", "/")


class AStorysPictures(unittest.TestCase):
    def test_newest_first_with_the_stage_that_took_it_and_nothing_but_pictures(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shots = os.path.join(root, ".dca-factory", "runs", "S-1", "shots")
        os.makedirs(shots)
        for name, moment in (("test-the-queue.png", 100), ("judge-the-desk.png", 200), ("notes.txt", 300)):
            with open(os.path.join(shots, name), "wb") as out:
                out.write(PNG if name.endswith(".png") else b"text")
            os.utime(os.path.join(shots, name), (moment, moment))
        away = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, away, True)
        with open(os.path.join(away, "secret.png"), "wb") as out:
            out.write(PNG)
        os.symlink(os.path.join(away, "secret.png"), os.path.join(shots, "judge-away.png"))
        found = shots_of(root, ".dca-factory/runs", "S-1")
        self.assertEqual(["judge-the-desk.png", "test-the-queue.png"], [s.name.value for s in found])
        self.assertEqual(["judge", "test"], [s.taker.value for s in found])
        self.assertEqual(".dca-factory/runs/S-1/shots/judge-the-desk.png", found[0].path.value)

    def test_a_story_without_pictures_has_none(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        self.assertEqual([], shots_of(root, ".dca-factory/runs", "S-2"))


class TheRunnerCollectsWhatATestTook(unittest.TestCase):
    """After a test command the gate runs for a story, the pictures that run saved in the profile's `screenshots:`
    folder are the story's — whatever language or runner took them (WP-184)."""

    def project(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def test_a_picture_the_run_made_is_copied_and_an_older_one_is_not(self):
        root = self.project()
        folder = os.path.join(root, "build", "shots")
        os.makedirs(os.path.join(folder, "checkout"))
        old = os.path.join(folder, "yesterday.png")
        for path in (old, os.path.join(folder, "checkout", "review.png"), os.path.join(folder, "trace.zip")):
            with open(path, "wb") as out:
                out.write(PNG if path.endswith(".png") else b"PK")
        os.utime(old, (time.time() - 86400, time.time() - 86400))
        story = os.path.join(root, ".dca-factory", "runs", "S-1")
        copied = collect_shots(root, "build/shots", story, "e2eTest", Instant(time.time() - 60))
        self.assertEqual(["e2e-checkout-review.png"], copied)
        self.assertEqual(["e2e-checkout-review.png"], os.listdir(os.path.join(story, "shots")))

    def test_a_test_command_the_gate_runs_brings_its_pictures_to_the_story(self):
        root = self.project()
        script = os.path.join(root, "take.py")
        with open(script, "w") as out:
            out.write("import os\nos.makedirs('shots', exist_ok=True)\n"
                      f"open('shots/after-the-login.png', 'wb').write({PNG!r})\n")
        profile = {"e2eTest": f"{PYTHON} take.py", "screenshots": "shots", "testEvidence": "exit-code"}
        suite_run(root, profile, "e2eTest", profile["e2eTest"], SuiteOwner(os.path.join(root, "runs"), "S-1", {}))
        self.assertEqual(["e2e-after-the-login.png"], [s.name.value for s in shots_of(root, "runs", "S-1")])

    def test_without_the_profile_key_nothing_is_collected(self):
        root = self.project()
        script = os.path.join(root, "take.py")
        with open(script, "w") as out:
            out.write(f"import os\nos.makedirs('shots', exist_ok=True)\nopen('shots/a.png', 'wb').write({PNG!r})\n")
        profile = {"e2eTest": f"{PYTHON} take.py", "testEvidence": "exit-code"}
        suite_run(root, profile, "e2eTest", profile["e2eTest"], SuiteOwner(os.path.join(root, "runs"), "S-1", {}))
        self.assertEqual([], shots_of(root, "runs", "S-1"))


if __name__ == "__main__":
    unittest.main()
