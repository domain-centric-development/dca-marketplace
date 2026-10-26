"""End the factory after its running stage, or at once."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess


@dataclasses.dataclass(frozen=True)
class StopFactoryCommand:
    now: bool = False
    wait: bool = True
    by: str = ""


class StopFactoryInputPort(UseCase[StopFactoryCommand, int], typing.Protocol):
    """Its exit."""


class StopFactoryUseCase:
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, command: StopFactoryCommand) -> int:
        return self._process.down(command.now, command.wait, command.by)
