"""Who works in the checkout: the worker, since when, how it was started, whether it lives."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.factory_process import FactoryProcess, Info


@dataclasses.dataclass(frozen=True)
class ShowWorkerQuery:
    """No field: the checkout is the one asked."""


class ShowWorkerInputPort(UseCase[ShowWorkerQuery, typing.Tuple[typing.Optional[Info], str]], typing.Protocol):
    """The worker's facts (None: nobody) and its line."""


class ShowWorkerUseCase:
    def __init__(self, process: FactoryProcess) -> None:
        self._process = process

    def execute(self, command: ShowWorkerQuery) -> typing.Tuple[typing.Optional[Info], str]:
        info = self._process.worker()
        return info, self._process.worker_line(info)
