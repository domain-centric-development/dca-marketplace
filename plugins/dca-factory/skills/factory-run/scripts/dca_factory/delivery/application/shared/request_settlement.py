"""Whether a request still holds, and the requests the factory settles itself, without a tool."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from .requests import Kind, Request


class RequestSettlement(OutputPort, typing.Protocol):
    """The checks and use cases a request reaches without a skill."""

    def holds(self, kind: Kind, fields: typing.Mapping[str, str], words: str) -> None:
        """Nothing where what held when the request was written still holds; RequestRefused, saying why, where not."""
        ...

    def settle(self, request: Request, at: str) -> typing.Optional[typing.List[str]]:
        """The ids of what settling it wrote, or None where a skill must work it; RequestRefused where it cannot."""
        ...
