"""A project's layout and its git ignores, as the pipeline keeps them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class ProjectUpkeep(OutputPort, typing.Protocol):
    def migrate(self) -> int:
        """An older layout moved to one owner per place, every move said; its exit."""
        ...

    def journals_into_git(self) -> typing.Optional[str]:
        """The `.gitignore` line that ignores the pipeline's folder made into lines that keep everything out but the
        story journals; where the journals are when it changed something, else None."""
        ...
