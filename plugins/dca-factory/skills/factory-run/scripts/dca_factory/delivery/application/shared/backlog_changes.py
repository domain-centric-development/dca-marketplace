"""What a request changed in the main checkout, and its commit — the backlog's and the description's, never code."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort


@dataclasses.dataclass(frozen=True)
class Committed:
    """A commit made — its short id —, or why it was refused (`refusal`)."""

    head: str
    refusal: str


class BacklogChanges(OutputPort, typing.Protocol):
    """The main checkout's changes."""

    def dirty(self) -> typing.Dict[str, str]:
        """{path: digest} of everything changed or new outside the factory's folder — a story's records included."""
        ...

    def people(self, paths: typing.Iterable[str]) -> typing.Set[str]:
        """The paths that are what a request may write and the factory commits: the backlog and the description."""
        ...

    def commit(self, paths: typing.Sequence[str], message: str) -> Committed:
        """The paths committed alone, with the stories' journals beside them, through the commit hook."""
        ...
