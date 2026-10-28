"""The decision records a request's skill wrote to ask a person, and the question pass on the drafts it wrote."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class RequestRecords(OutputPort, typing.Protocol):
    """The records of the requests."""

    def asked(self, request: str) -> typing.List[typing.Tuple[str, str, str]]:
        """Every record the request wrote to ask: (where, as a person reads it; its id; its state)."""
        ...

    def applied(self, request: str) -> None:
        """Every answered record of the request stamped applied."""
        ...

    def questioned(self, paths: typing.Sequence[str], request: str) -> None:
        """The drafts the request wrote carry the question pass that ran on them as they stand."""
        ...
