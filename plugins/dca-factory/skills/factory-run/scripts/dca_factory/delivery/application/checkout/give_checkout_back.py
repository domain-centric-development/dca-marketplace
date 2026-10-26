"""Give the checkout back — the owner's, or this session's."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.checkout import Checkout


@dataclasses.dataclass(frozen=True)
class GiveCheckoutBackCommand:
    owner: typing.Optional[str] = None


class GiveCheckoutBackInputPort(UseCase[GiveCheckoutBackCommand, int], typing.Protocol):
    """Its exit."""


class GiveCheckoutBackUseCase:
    def __init__(self, port: Checkout) -> None:
        self._port = port

    def execute(self, command: GiveCheckoutBackCommand) -> int:
        self._port.freeze_windows()
        return self._port.release(command.owner)
