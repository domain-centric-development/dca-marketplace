"""The light paths stay light: what `factory.sh` and the runner ask many times per story loads a part of the package,
not all of it (WP-197). A module imported at the top of one of these paths would pull hundreds back in unnoticed —
the answer stays right, only every call slows down — so the count of the package's modules each one loads is held
here, with room for growth, against the whole command line's."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SCRIPTS

#: (entry point, arguments, at most this many of the package's modules)
LIGHT = (
    ("factory-cli.py", ["--stages", "--shell", "--place", "runs"], 90),     # factory.sh, at every start
    ("factory-cli.py", ["--get", "model"], 90),                             # the runner's profile questions
    ("story-gate.py", ["--owned", "start", "plan", "--story", "S-1"], 110),  # every stage window, twice
    ("story-gate.py", ["--record-base", "--story", "S-1"], 110),
    ("story-gate.py", ["--check-contract"], 170),                           # factory.sh, before every run
)


def loaded(entry, argv, cwd):
    """How many of the package's modules a fresh process of <entry> <argv> imports."""
    ran = subprocess.run([sys.executable, "-X", "importtime", os.path.join(SCRIPTS, entry), *argv], cwd=cwd,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return sum(1 for line in ran.stderr.splitlines() if line.startswith("import time:") and "dca_factory" in line)


class LightPaths(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_the_whole_command_line_is_counted_as_heavy(self):
        self.assertGreater(loaded("factory-cli.py", ["--status"], self.root), 250)

    def test_each_light_path_loads_a_part_of_the_package(self):
        for entry, argv, most in LIGHT:
            with self.subTest(command=" ".join([entry, *argv])):
                self.assertLessEqual(loaded(entry, argv, self.root), most)


if __name__ == "__main__":
    unittest.main()
