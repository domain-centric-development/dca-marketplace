"""The gate in the runner's process (WP-197): only where the runner's package is the gate's by content, as its own
process would end — its places put back, its exit, its failure — and otherwise the process it always was."""

import os
import shutil
import sys
import tempfile
import types
import unittest

from support import SCRIPTS
from dca_factory.delivery.adapter.outgoing.process.gate_process import GateProcess
from dca_factory.delivery.adapter.outgoing.process.runner_process import Run
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles


class Host:
    """A run as the gate's adapter sees it: whether the gate may run here, and what was started."""

    def __init__(self, here):
        self.here = here
        self.gate_path = __file__
        self.started = []
        self.called = []

    def runs_the_gate(self, gate_path):
        return self.here

    def gate_here(self, argv, *, quiet=False):
        self.called.append((list(argv), quiet))
        return 0

    def run(self, argv, **kwargs):
        self.started.append(argv)
        return 0, ""


class Routing(unittest.TestCase):

    def test_the_same_package_runs_the_gate_here(self):
        host = Host(here=True)
        GateProcess(host).owned("start", "plan", "STORY-1")
        GateProcess(host).record("--record-base", "STORY-1")
        self.assertEqual(host.started, [])
        self.assertEqual(host.called, [(["--owned", "start", "plan", "--story", "STORY-1"], False),
                                       (["--record-base", "--story", "STORY-1"], True)])

    def test_another_package_starts_the_gate_process(self):
        host = Host(here=False)
        GateProcess(host).owned("end", "plan", "STORY-1", 0)
        self.assertEqual(host.called, [])
        self.assertEqual(host.started, [[sys.executable, __file__, "--owned", "end", "plan", "0", "--story", "STORY-1"]])


def a_run(scripts, cases=object()):
    """The parts of a run `runs_the_gate` and `gate_here` read."""
    run = types.SimpleNamespace(_cases=cases, scripts=scripts, home=scripts, same_gate={}, own_digest=None)
    run.pipeline_hash = lambda folder=None, names=(): Run.pipeline_hash(run, folder, names)
    return run


class SamePackage(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.environ.pop("FACTORY_GATE_PROCESS", None)

    def installed(self, name):
        folder = os.path.join(self.root, name)
        for part in ("dca_factory", "workflow"):
            shutil.copytree(os.path.join(SCRIPTS, part), os.path.join(folder, part),
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(os.path.join(SCRIPTS, "story-gate.py"), folder)
        return os.path.join(folder, "story-gate.py")

    def test_a_copy_alike_by_content_runs_here(self):
        self.assertTrue(Run.runs_the_gate(a_run(SCRIPTS), self.installed("copy")))

    def test_a_changed_module_keeps_the_process(self):
        gate = self.installed("changed")
        with open(os.path.join(os.path.dirname(gate), "dca_factory", "contract.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# changed\n")
        self.assertFalse(Run.runs_the_gate(a_run(SCRIPTS), gate))

    def test_the_switch_and_a_run_without_its_use_cases_keep_the_process(self):
        gate = self.installed("copy")
        self.assertFalse(Run.runs_the_gate(a_run(SCRIPTS, cases=None), gate))
        os.environ["FACTORY_GATE_PROCESS"] = "1"
        self.addCleanup(os.environ.pop, "FACTORY_GATE_PROCESS", None)
        self.assertFalse(Run.runs_the_gate(a_run(SCRIPTS), gate))


class AsItsProcessWouldEnd(unittest.TestCase):

    def gate_here(self, gate, quiet=False):
        run = a_run(SCRIPTS, cases=types.SimpleNamespace(gate_here=gate))
        run.cases = run._cases
        return Run.gate_here(run, ["--story", "S"], quiet=quiet)

    def test_the_places_it_set_are_put_back(self):
        before = dict(profiles.PLACES)

        def sets_its_own(argv):
            profiles.PLACES["runs"] = "elsewhere/runs"
            return 0
        self.assertEqual(self.gate_here(sets_its_own), 0)
        self.assertEqual(profiles.PLACES, before)

    def test_an_exit_is_its_code_and_a_failure_exit_1(self):
        def exits(argv):
            raise SystemExit(2)

        def fails(argv):
            raise ValueError("broken")
        self.assertEqual(self.gate_here(exits), 2)
        self.assertEqual(self.gate_here(fails, quiet=True), 1)


if __name__ == "__main__":
    unittest.main()
