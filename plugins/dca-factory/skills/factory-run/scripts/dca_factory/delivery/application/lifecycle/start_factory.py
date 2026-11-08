"""Start the factory as a process of its own, in the background — the runner watching the backlog, its page beside it where asked."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess


@dataclasses.dataclass(frozen=True)
class StartFactoryCommand:
    run_args: typing.Tuple[str, ...] = ()
    serve: bool = False
    port: typing.Optional[int] = None
    by: str = ""
    #: the backlog on (`up`); False: the worker for a person's requests alone, as the page starts it (WP-177)
    backlog: bool = True


class StartFactoryInputPort(UseCase[StartFactoryCommand, int], typing.Protocol):
    """Its exit."""


class StartFactoryUseCase(StartFactoryInputPort):
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, command: StartFactoryCommand) -> int:
        return self._process.up(command.run_args, command.serve, command.port, command.by, command.backlog)
