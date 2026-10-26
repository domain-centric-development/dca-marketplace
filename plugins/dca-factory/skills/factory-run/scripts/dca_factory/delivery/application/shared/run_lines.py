"""What the runner says while it works — a line for the person who follows the run, or one about a stop."""

from __future__ import annotations

import typing


class RunLines(typing.Protocol):
    """The run's lines as a person follows them."""

    def out(self, line: str) -> None:
        """A line about what the run does."""
        ...

    def err(self, line: str) -> None:
        """A line about what stopped, failed or was set aside."""
        ...
