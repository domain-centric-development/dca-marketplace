"""Start the factory's page detached — or name the one that runs already; a second page per checkout is never started."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess, Info


@dataclasses.dataclass(frozen=True)
class StartPageCommand:
    port: typing.Optional[int] = None


@dataclasses.dataclass(frozen=True)
class PageStart:
    """The page that runs already (nothing started) — or the exit of the start."""

    running: typing.Optional[Info]
    exit: int


class StartPageInputPort(UseCase[StartPageCommand, PageStart], typing.Protocol):
    """The running page, or the new one's exit."""


class StartPageUseCase:
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, command: StartPageCommand) -> PageStart:
        running = self._process.running_page()
        if running:
            return PageStart(running, 0)
        return PageStart(None, self._process.start_page(command.port))
