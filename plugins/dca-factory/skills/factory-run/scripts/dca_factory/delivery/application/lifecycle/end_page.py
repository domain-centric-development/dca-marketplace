"""End the factory's page — and with it the worker of a person's requests, where `up` has not the backlog on (WP-177)."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess


@dataclasses.dataclass(frozen=True)
class EndPageCommand:
    pass


class EndPageInputPort(UseCase[EndPageCommand, int], typing.Protocol):
    """Its exit: 0 when no page runs any more."""


class EndPageUseCase(EndPageInputPort):
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, command: EndPageCommand) -> int:
        return self._process.end_page()
