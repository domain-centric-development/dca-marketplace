"""The page this checkout runs already, if any — a second one is never started beside it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess, Info


@dataclasses.dataclass(frozen=True)
class ShowRunningPageQuery:
    """No field: the checkout is the one asked."""


class ShowRunningPageInputPort(UseCase[ShowRunningPageQuery, typing.Optional[Info]], typing.Protocol):
    """The running page (pid, port, url), or None."""


class ShowRunningPageUseCase:
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, query: ShowRunningPageQuery) -> typing.Optional[Info]:
        return self._process.running_page()
