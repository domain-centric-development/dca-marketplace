"""Say that this session looked at the backlog — a listening loop's sign of life."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.checkout import Checkout


@dataclasses.dataclass(frozen=True)
class MarkListeningCommand:
    """No field: the session is the one it runs in."""


class MarkListeningInputPort(UseCase[MarkListeningCommand, int], typing.Protocol):
    """Its exit."""


class MarkListeningUseCase:
    def __init__(self, port: Checkout) -> None:
        self._port = port

    def execute(self, command: MarkListeningCommand) -> int:
        self._port.freeze_windows()
        return self._port.listening()
