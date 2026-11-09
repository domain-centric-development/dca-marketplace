"""Bring the project up to the newest pipeline found, for exactly the tools it already has, keeping links as links and
copies as copies. The profile is the project's and is never rewritten; a file contract that moved is said out loud,
with the profile line to raise. The replacing is the newest runner's, not this one's: a release that adds a file the
project needs must be able to put it there, even when the project's runner predates it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.pipeline_install import PipelineInstall, SkillMode
from .install_steps import install


@dataclasses.dataclass(frozen=True)
class RefreshPipeline:
    source: typing.Optional[str]
    mode: typing.Optional[SkillMode]
    adopt: typing.Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Updated:
    """The project's copy of the pipeline replaced from <source>."""

    source: str


@dataclasses.dataclass(frozen=True)
class HandedOver:
    """The newest pipeline's runner did the update; its exit."""

    code: int


Refresh = typing.Union[Updated, HandedOver]


class RefreshPipelineInputPort(UseCase[RefreshPipeline, Refresh], typing.Protocol):
    """What the update did."""


class RefreshPipelineUseCase(RefreshPipelineInputPort):
    def __init__(self, install_port: PipelineInstall) -> None:
        self._port = install_port

    def execute(self, command: RefreshPipeline) -> Refresh:
        port = self._port
        source = port.update_source(command.source)
        runner = port.runner_of(source)
        if runner is not None:
            return HandedOver(port.hand_over(runner, command.mode, command.adopt, source))
        before = port.stamp()
        updated = False
        for tool in port.tools():
            for folder in port.tool_folders(tool) or []:
                mode = port.skills_mode(folder)
                if mode is None:
                    continue
                # the mode the project has — unless the person names the other one, which is how a project switches
                install(port, tool, source, command.mode or mode, command.adopt)
                updated = True
        if not updated:
            install(port, "none", source, SkillMode.LINK if command.mode is SkillMode.LINK else None, command.adopt)
        port.prune_renamed(source)
        port.updated(before, source)
        return Updated(source)
