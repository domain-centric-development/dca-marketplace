"""Set the pipeline up where it is not: idempotent — an installed pipeline is the update's to replace, and only a tool
named that has no skills here yet is what setup adds, from the same release."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.pipeline_install import PipelineInstall, SkillMode
from .install_steps import install


@dataclasses.dataclass(frozen=True)
class InstallPipeline:
    tool: typing.Optional[str]
    source: typing.Optional[str]
    mode: typing.Optional[SkillMode]
    adopt: typing.Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Installed:
    """The pipeline installed — for every tool, or the one added."""


@dataclasses.dataclass(frozen=True)
class AlreadyInstalled:
    """The pipeline is here: setup installs nothing."""


@dataclasses.dataclass(frozen=True)
class OtherRelease:
    """Adding the tool would also replace the installed pipeline (<have>) with another release (<new>): refused."""

    have: str
    new: str


Install = typing.Union[Installed, AlreadyInstalled, OtherRelease]


class InstallPipelineInputPort(UseCase[InstallPipeline, Install], typing.Protocol):
    """What the setup did."""


class InstallPipelineUseCase(InstallPipelineInputPort):
    def __init__(self, install_port: PipelineInstall) -> None:
        self._port = install_port

    def execute(self, command: InstallPipeline) -> Install:
        port = self._port
        if not port.installed():
            install(port, command.tool or "all", command.source, command.mode, command.adopt)
            return Installed()
        folders = port.tool_folders(command.tool) if command.tool else None
        if not folders or any(port.skills_mode(folder) is not None for folder in folders):
            return AlreadyInstalled()
        # Adding a tool installs the gate, runner and hook as well: from another version that is an update nobody
        # asked for, so it is refused and named.
        source = port.tool_source(command.source)
        have, new = port.version_of(None), port.version_of(source) if source else ""
        if new and new != have:
            return OtherRelease(have, new)
        install(port, command.tool or "all", command.source, command.mode, command.adopt)
        return Installed()
