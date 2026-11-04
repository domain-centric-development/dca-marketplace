"""The factory's own log — the worker's lines (WP-183): a file of the factory's folder today."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class FactoryLog(OutputPort, typing.Protocol):
    def size(self) -> typing.Optional[int]:
        """How much the log holds now — None where the factory has written none yet."""
        ...

    def read(self, offset: int) -> typing.Tuple[str, int]:
        """What the log holds from `offset` on, and where it ends."""
        ...
