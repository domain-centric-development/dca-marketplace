"""What the shell runner reads once at its start besides the stage table: the tool table, the places."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class RunnerTables(OutputPort, typing.Protocol):
    def tool_lines(self) -> typing.Optional[typing.List[str]]:
        """The tool records as the runner's assignments; None where a record holds a value no shell takes as a word
        (said already)."""
        ...

    def place(self, key: str) -> str:
        """Where the factory reads <key> — the profile's, else its default."""
        ...
