"""The pipeline in a project as the setup and the update change it: where a pipeline is found, the tools' skill
folders, the pipeline's own files, the stack profile from detection — each step saying what it did as it does it."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import OutputPort, OutputPortException


class Stop(enum.Enum):
    """Why an install stopped: a step that had to work did not (the project is unchanged from there on), a refusal
    before anything changed, or a tool the factory has no record of."""

    FAILED = "failed"
    REFUSED = "refused"
    USAGE = "usage"


class InstallStopped(OutputPortException):
    """A step that cannot go on, said already: nothing more is changed."""

    def __init__(self, why: Stop) -> None:
        super().__init__(why.value)
        self.why = why


class Proposal(enum.Enum):
    """What detection proposes against the profile, said in full (a table and what to do) or in the status's lines."""

    FULL = "full"
    BRIEF = "brief"


class ProfileOutcome(enum.Enum):
    """The profile against detection: it declares what detection finds, it lacks a key (or there is no runner or no
    profile), or the step was refused."""

    HOLDS = "holds"
    LACKS = "lacks"
    REFUSED = "refused"


class SkillMode(enum.Enum):
    """How the project holds a tool's skills: linked into a checkout or a cache, or copies of its own."""

    LINK = "link"
    COPY = "copy"


class PipelineInstall(OutputPort, typing.Protocol):
    """The installer, working in the project's root folder."""

    def install_source(self, named: typing.Optional[str]) -> str:
        """The pipeline's skill folder to install from: <named>, the one this runner belongs to, else the newest found;
        InstallStopped where there is none."""
        ...

    def update_source(self, named: typing.Optional[str]) -> str:
        """The pipeline's skill folder to update from: <named>, else the newest found — refused where the one found is
        older than the installed one, or lies inside the project (InstallStopped)."""
        ...

    def runner_of(self, source: str) -> typing.Optional[str]:
        """The runner of the pipeline at <source> where it is another than the one running now; None where it is this
        one, or where an update was handed over already."""
        ...

    def hand_over(self, runner: str, mode: typing.Optional[SkillMode], adopt: typing.Sequence[str], source: str) -> int:
        """The update run by <runner>, the newest pipeline's: a release that adds a file the project needs puts it
        there, even when the project's runner predates it. Its exit."""
        ...

    def tool_folders(self, tool: str) -> typing.Optional[typing.List[str]]:
        """The skill folders of <tool> — every tool's for `all`, none for `none`; None for a tool the factory has no
        record of."""
        ...

    def tools(self) -> typing.List[str]:
        """The tools the factory has a record of."""
        ...

    def holds_plugins(self, folder: str) -> bool:
        """The tool of <folder> loads the method skills from its plugins (Claude Code's)."""
        ...

    def skills_mode(self, folder: str) -> typing.Optional[SkillMode]:
        """How the project holds the skills in <folder>; None for a tool it does not use."""
        ...

    def cache_source(self, source: str) -> bool:
        """<source> is a plugin cache's — versioned, and a version is removed some time after an update."""
        ...

    def can_link(self) -> bool:
        """A link made here is a link (Windows needs developer mode for one)."""
        ...

    def prepare(self, source: str) -> None:
        """The pipeline's folders, an older layout moved, a first stack profile from detection."""
        ...

    def fill(self, folder: str, source: str, mode: SkillMode, reason: str, adopt: typing.Sequence[str]) -> None:
        """The pipeline's skills (and, for a tool without plugins, the method skills beside it) into <folder>."""
        ...

    def refresh_carriers(self, folder: str, source: str, mode: SkillMode) -> None:
        """The carriers the profile names, into <folder>."""
        ...

    def write_ignores(self, folder: str, mode: SkillMode) -> None:
        """The ignore lines of <folder>'s links — none for copies."""
        ...

    def copy_pipeline(self, source: str) -> None:
        """The architecture governance named, the pipeline's own files copied in and stamped, the commit hook's path
        set."""
        ...

    def allow_commands(self) -> None:
        """Claude Code's allow list: the gate, the cli, the profile's commands, the reading verbs."""
        ...

    def project_lines(self) -> None:
        """The merge and ignore lines, the journals let in, the instruction block in AGENTS.md."""
        ...

    def closing(self, folders: typing.Sequence[str], source: str, mode: SkillMode) -> None:
        """What the install leaves to the person: how the skills travel with the project."""
        ...

    def installed(self) -> bool:
        """The gate and the runner are in the project."""
        ...

    def stamp(self) -> typing.Tuple[str, str]:
        """The installed (version, contract), "" where the stamp has none."""
        ...

    def version_of(self, source: typing.Optional[str]) -> str:
        """The version of the pipeline at <source> — the installed one for None; "" where none is found."""
        ...

    def tool_source(self, named: typing.Optional[str]) -> typing.Optional[str]:
        """The skill folder a tool would be added from: <named>, the one this runner belongs to, the newest found."""
        ...

    def prune_renamed(self, source: str) -> None:
        """Copies under a name the method plugins renamed, removed where nobody edited them."""
        ...

    def updated(self, before: typing.Tuple[str, str], source: str) -> None:
        """The update said, the backlog's dates filled in, what the profile should raise or add named."""
        ...

    def check_detected(self, proposal: Proposal) -> ProfileOutcome:
        """What detection finds against the profile, said; read-only in every state."""
        ...

    def write_detected(self, key: typing.Optional[str]) -> ProfileOutcome:
        """What detection finds and the profile lacks, written — and <key>'s detected value over the profile's; the
        carriers a written line names put where the stages find them."""
        ...
