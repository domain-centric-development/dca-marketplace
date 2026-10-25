"""What the help reads of the project itself: whether it is described and has a build, where its parts are."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class ProjectFacts(OutputPort, typing.Protocol):
    """The project as its help reads it."""

    def profile_file(self) -> typing.Optional[str]:
        """The stack profile in use, as a person reads its path — None where the project has none."""
        ...

    def profile_name(self) -> str:
        """The stack profile's file name where the project has none yet."""
        ...

    def place(self, key: str) -> str:
        """Where the project keeps one part — `product`, `tech`, `domain`, `spec`, `epics`, `runs`, `decisions` (the
        folder beside a story) — as a person reads it."""
        ...

    def described(self) -> bool:
        """Whether the product and the technical decisions are written."""
        ...

    def has_build(self) -> bool:
        """Whether the project has a build file a stack is known by."""
        ...
