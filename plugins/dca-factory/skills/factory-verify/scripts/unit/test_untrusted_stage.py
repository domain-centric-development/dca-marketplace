"""A story whose text came from outside runs its stages offline, without the web and without a secret: the tool is
started with its offline flags and an environment without a variable that names one — its own sign-in kept."""

import os
import stat
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.tools.tool_choice import ToolChoice
from dca_factory.delivery.adapter.outgoing.tools.tool_processes import ToolProcesses
from dca_factory.delivery.domain.model.reach import Reach

FAKE = """#!/bin/sh
echo "$@" > "$FAKE_OUT.args"
env > "$FAKE_OUT.env"
"""


class Host:
    worker, runs, stop_file, request_in_flight, timeout = "w", ".dca-factory/runs", "stop", "", 0
    add_dirs, read_dirs = [], []

    def __init__(self, reach):
        self._reach = reach

    def protected_dirs(self):
        return []

    def guarded_walls(self, story):
        return []

    def stage_reach(self, story):
        return self._reach

    def skill_reach(self):
        return []

    def journal_line(self, story, line):
        pass

    def renew(self):
        return True

    def sleep(self, seconds):
        pass

    def wait(self, process, timeout=None):
        return process.wait(timeout=timeout)


class UntrustedStage(unittest.TestCase):

    def run_tool(self, reach):
        with tempfile.TemporaryDirectory() as folder:
            binary = os.path.join(folder, "codex")
            with open(binary, "w", encoding="utf-8") as handle:
                handle.write(FAKE)
            os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)
            out = os.path.join(folder, "seen")
            environment = {"PATH": f"{folder}{os.pathsep}{os.environ['PATH']}", "FAKE_OUT": out,
                           "SERVICE_API_TOKEN": "s3cret", "OPENAI_API_KEY": "own", "FACTORY_ISOLATION": "off"}
            with mock.patch.dict(os.environ, environment, clear=False):
                os.environ.pop("FACTORY_TOOL_CMD", None)
                choice = ToolChoice(lambda: {}, "python3", ".agents/factory/story-gate.py")
                code = ToolProcesses(Host(reach), choice).invoke_once("codex", "the prompt", os.devnull, "build", "S-1")
            with open(out + ".args", encoding="utf-8") as handle:
                args = handle.read()
            with open(out + ".env", encoding="utf-8") as handle:
                env = handle.read()
            return code, args, env

    def test_an_untrusted_stage_is_offline_and_has_no_secret_but_the_tools_own_sign_in(self):
        code, args, env = self.run_tool(Reach.untrusted_stage())
        self.assertEqual(code, 0)
        self.assertIn("permissions.factory.network.enabled=false", args)
        self.assertNotIn("SERVICE_API_TOKEN", env)
        self.assertIn("OPENAI_API_KEY=own", env)

    def test_a_persons_story_keeps_the_network_and_its_environment(self):
        code, args, env = self.run_tool(Reach.stage())
        self.assertEqual(code, 0)
        self.assertIn("permissions.factory.network.enabled=true", args)
        self.assertIn("SERVICE_API_TOKEN=s3cret", env)


if __name__ == "__main__":
    unittest.main()
