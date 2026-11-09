"""`factory.sh` hands over at once (WP-202 step 3): the script asks a Python for its version and becomes the package's
command line, which runs the cli's and the gate's command lines in its process — the gate as its own process only
where the project's gate is another release. What the script and the installer read of a release keeps the shell's
meaning: versions ordered as `sort -V` orders them, the usage the script's header."""

import os
import re
import shutil
import tempfile
import unittest

from support import SCRIPTS

from dca_factory.delivery.adapter.outgoing.install import sources
from dca_factory.infrastructure import shell


class TheScriptHandsOver(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(SCRIPTS, "factory.sh"), encoding="utf-8") as handle:
            self.code = [line for line in handle.read().splitlines() if line.strip() and not line.lstrip().startswith("#")]

    def test_it_starts_a_python_only_for_its_version_and_to_hand_over(self):
        # a line that runs the Python found, or a candidate (`fits`) — as the command, not as an argument
        started = [line.strip() for line in self.code
                   if re.search(r'(?:^\s*|[;&|{]\s*|exec\s+)"\$(?:PY|1)"\s', line)]
        self.assertEqual(['fits() { "$1" -c \'import sys; sys.exit(sys.version_info < (3, 12))\' >/dev/null 2>&1; }',
                          'exec "$PY" "$CLI" --sh "$PY" "$@"'], started)

    def test_it_decides_no_verb_of_its_own(self):
        verbs = [line.strip() for line in self.code if re.match(r"\s*(status|run|backlog|check|verify)\)", line)]
        self.assertEqual([], verbs)


class Versions(unittest.TestCase):

    def test_ordered_as_sort_v_orders_them(self):
        self.assertEqual("0.10.0", sources.later("0.9.0", "0.10.0"))
        self.assertEqual("0.156.0", sources.later("0.156.0", "0.155.9"))
        self.assertEqual("9.9.9-0.156.0", sources.later("0.156.0", "9.9.9-0.156.0"))
        self.assertEqual("0.1.0", sources.later("", "0.1.0"))

    def test_a_tie_is_no_newer(self):
        self.assertFalse(sources.newer("0.156.0", "0.156.0"))
        self.assertTrue(sources.newer("0.157.0", "0.156.0"))


class TheGateInItsProcess(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        folder = os.path.join(self.root, ".agents", "factory")
        os.makedirs(folder)
        shutil.copy(os.path.join(SCRIPTS, "story-gate.py"), folder)
        for name in ("dca_factory", "workflow"):
            shutil.copytree(os.path.join(SCRIPTS, name), os.path.join(folder, name),
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.contract = os.path.join(folder, "dca_factory", "contract.py")
        os.chdir(self.root)

    def test_the_same_release_runs_here(self):
        self.assertTrue(shell.ShellCall("python3").gate_here())

    def test_another_release_runs_as_its_own_process(self):
        with open(self.contract, "a", encoding="utf-8") as handle:
            handle.write("\n# another release\n")
        self.assertFalse(shell.ShellCall("python3").gate_here())

    def test_a_process_is_asked_for_by_name(self):
        os.environ["FACTORY_GATE_PROCESS"] = "1"
        self.addCleanup(os.environ.pop, "FACTORY_GATE_PROCESS", None)
        self.assertFalse(shell.ShellCall("python3").gate_here())


class TheUsage(unittest.TestCase):

    def test_is_the_scripts_header_without_the_tool_note(self):
        header = shell.ShellCall("python3").runner_header()
        self.assertTrue(header[0].startswith("# The factory outside the session"), header[:1])
        self.assertTrue(any("factory.sh setup [--tool" in line for line in header))
        self.assertFalse(any("FACTORY_TOOL_CMD replaces" in line for line in header))


if __name__ == "__main__":
    unittest.main()
