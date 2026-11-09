"""`factory.sh`'s composition root: the script found a Python and handed over (`factory-cli.py --sh <python> …`); its
command line gets the cli's and the gate's command lines in this process, the tool table from the records and the
installer's use cases — each built when the command asks for it (WP-202 step 3). Where the project's gate is another
release than this package, the gate runs as its own process, as the script ran it."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import traceback
import typing

from ..delivery.adapter.incoming.shell.shell_root import Captured
from ..delivery.adapter.outgoing.files.pipeline_digest import GATE_FILES, hashing, pipeline_digest
from ..delivery.adapter.outgoing.tools.agents import TOOLS
from ..sharedkernel.adapter.outgoing.profile.profile_files import (
    kept_places, place, read_profile, resolve_profile, set_places)

if typing.TYPE_CHECKING:
    # the installer and its use cases are loaded by the verbs that use them — a reading verb or a check pays for none
    from ..delivery.adapter.outgoing.install.installer import PipelineInstaller
    from ..delivery.application.setup.check_detected_profile import CheckDetectedProfileUseCase
    from ..delivery.application.setup.install_pipeline import InstallPipelineUseCase
    from ..delivery.application.setup.refresh_pipeline import RefreshPipelineUseCase
    from ..delivery.application.setup.write_detected_profile import WriteDetectedProfileUseCase

GATE = os.path.join(".agents", "factory", "story-gate.py")
SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
Entry = typing.Callable[[typing.List[str]], int]


def main(argv: typing.Sequence[str]) -> int:
    """<python> <verb> <flags…>: the script's command line, given the root it builds its use cases from."""
    from ..delivery.adapter.incoming.shell import shell_command
    shell_command.wire(ShellCall(argv[0] if argv else os.path.basename(sys.executable)))
    return shell_command.main(list(argv[1:]))


def entered(entry: Entry, argv: typing.Sequence[str], program: str) -> int:
    """A command line run here as its own process would end: its places and the working folder put back afterwards,
    the program's name its own, an exit it asks for its code, and a failure its traceback and exit 1."""
    named, cwd = sys.argv[0], os.getcwd()
    sys.argv[0] = program
    try:
        with kept_places():
            return entry(list(argv))
    except SystemExit as ended:
        if ended.code is None or isinstance(ended.code, int):
            return ended.code or 0
        print(ended.code, file=sys.stderr)
        return 1
    except Exception:                       # noqa: BLE001 — a crashed process would say the same and exit 1
        traceback.print_exc()
        return 1
    finally:
        sys.argv[0] = named
        sys.stdout.flush()
        sys.stderr.flush()
        if os.getcwd() != cwd:
            os.chdir(cwd)


def kept(entry: Entry, argv: typing.Sequence[str], program: str, merged: bool = False) -> Captured:
    out, said = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out if merged else said):
        code = entered(entry, argv, program)
    return code, out.getvalue(), said.getvalue()


def cli_entry(argv: typing.List[str]) -> int:
    from . import cli
    return cli.main(argv)


def gate_entry(argv: typing.List[str]) -> int:
    from ..delivery.adapter.outgoing.stack import commands
    from . import gate
    # what a gate's process starts without: the tools it found missing, the suite record of its last call
    commands.MISSING_TOOLS.clear()
    commands.SUITES_RECORD = None
    return gate.main(argv)


class ShellCall:
    """One call of `factory.sh`, run by <python>."""

    def __init__(self, python: str) -> None:
        self.python = python
        #: the skill folder this runner belongs to — the plugin's, or the project's own root for an installed copy
        self.own = os.path.abspath(os.path.join(SCRIPTS, "..", ".."))
        self.cli_program = os.path.join(SCRIPTS, "factory-cli.py")
        self._installer: typing.Optional["PipelineInstaller"] = None
        self._same_gate: typing.Optional[bool] = None

    # --- the command lines in this process ------------------------------------------------------------------------
    def cli(self, argv: typing.Sequence[str]) -> int:
        return entered(cli_entry, argv, self.cli_program)

    def cli_captured(self, argv: typing.Sequence[str], merged: bool = False) -> Captured:
        return kept(cli_entry, argv, self.cli_program, merged)

    def gate_here(self) -> bool:
        """The project's gate is this package — the same folder, or the same files by content (WP-197)."""
        if self._same_gate is None:
            folder = os.path.realpath(os.path.dirname(os.path.abspath(GATE)))
            if folder == os.path.realpath(SCRIPTS):
                self._same_gate = True
            elif os.environ.get("FACTORY_GATE_PROCESS") == "1" or not hashing():
                self._same_gate = False
            else:
                own = pipeline_digest(SCRIPTS, GATE_FILES)
                self._same_gate = bool(own) and own == pipeline_digest(folder, GATE_FILES)
        return self._same_gate

    def gate(self, argv: typing.Sequence[str]) -> int:
        if self.gate_here():
            return entered(gate_entry, argv, GATE)
        sys.stdout.flush()
        return subprocess.run([sys.executable, GATE, *argv]).returncode

    def gate_merged(self, argv: typing.Sequence[str]) -> typing.Tuple[int, str]:
        if self.gate_here():
            code, out, _said = kept(gate_entry, argv, GATE, merged=True)
            return code, out
        done = subprocess.run([sys.executable, GATE, *argv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
        return done.returncode, done.stdout

    def run(self, argv: typing.Sequence[str]) -> int:
        return entered(cli_entry, argv, self.cli_program)

    # --- the tool table, the pipelines on this machine -----------------------------------------------------------------
    def tool_names(self) -> typing.List[str]:
        return [tool.name for tool in TOOLS]

    def tool_skills(self, tool: str) -> str:
        return next((t.skills for t in TOOLS if t.name == tool), "")

    def tool_args(self, tool: str) -> str:
        name = next((t.args_env for t in TOOLS if t.name == tool), "")
        return os.environ.get(name, "") if name else ""

    def tool_dirs(self) -> typing.List[str]:
        return [tool.skills for tool in TOOLS]

    def pipeline_found(self) -> typing.Optional[str]:
        from ..delivery.adapter.outgoing.install.sources import plugin_skills
        return plugin_skills(self.own, self.tool_dirs())

    def freshness(self) -> None:
        from ..delivery.adapter.outgoing.install.installer import gate_freshness
        gate_freshness(self.own, self.tool_dirs())

    def profile_renames(self) -> typing.List[str]:
        return self.installer().profile_renames()

    def runner_header(self) -> typing.List[str]:
        """Line 2 to the line before `# FACTORY_TOOL_CMD`, as the script's usage always printed it."""
        try:
            with open(os.path.join(SCRIPTS, "factory.sh"), encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except OSError:
            return []
        shown: typing.List[str] = []
        for line in lines[1:]:
            if line.startswith("# FACTORY_TOOL_CMD"):
                return shown
            shown.append(line)
        return shown[:-1]

    # --- the installer -----------------------------------------------------------------------------------------------
    def installer(self) -> "PipelineInstaller":
        from ..delivery.adapter.outgoing.install.installer import PipelineInstaller, ToolFolder
        if self._installer is None:
            folders = [ToolFolder(tool.name, tool.skills, tool.plugins) for tool in TOOLS]
            self._installer = PipelineInstaller(self.python, self.own, folders, self.cli_captured, self.runs())
        return self._installer

    @staticmethod
    def runs() -> str:
        """Where the run artefacts go, as the profile says when the call starts."""
        cwd = os.getcwd()
        with kept_places():
            set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))
            return place("runs")

    def set_up(self) -> InstallPipelineUseCase:
        from ..delivery.application.setup.install_pipeline import InstallPipelineUseCase
        return InstallPipelineUseCase(self.installer())

    def update(self) -> RefreshPipelineUseCase:
        from ..delivery.application.setup.refresh_pipeline import RefreshPipelineUseCase
        return RefreshPipelineUseCase(self.installer())

    def check_detected(self) -> CheckDetectedProfileUseCase:
        from ..delivery.application.setup.check_detected_profile import CheckDetectedProfileUseCase
        return CheckDetectedProfileUseCase(self.installer())

    def write_detected(self) -> WriteDetectedProfileUseCase:
        from ..delivery.application.setup.write_detected_profile import WriteDetectedProfileUseCase
        return WriteDetectedProfileUseCase(self.installer())
