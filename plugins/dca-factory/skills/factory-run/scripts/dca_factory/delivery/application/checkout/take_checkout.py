"""Take the checkout for one worker — renewed where it holds it, taken over where the holder is gone, refused where another works."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.checkout import Checkout


@dataclasses.dataclass(frozen=True)
class TakeCheckoutCommand:
    owner: str


class TakeCheckoutInputPort(UseCase[TakeCheckoutCommand, int], typing.Protocol):
    """Its exit."""


class TakeCheckoutUseCase:
    def __init__(self, port: Checkout) -> None:
        self._port = port

    def execute(self, command: TakeCheckoutCommand) -> int:
        self._port.freeze_windows()
        return self._port.claim(command.owner)
