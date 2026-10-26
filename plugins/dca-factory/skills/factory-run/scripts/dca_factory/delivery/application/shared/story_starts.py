"""Where a story begins when nobody names a stage — the schedule's view of that one story."""

from __future__ import annotations

import typing

#: (state, the stage it starts from or None, detail)
Start = typing.Tuple[str, typing.Optional[str], str]


class StoryStarts(typing.Protocol):
    """The schedule, asked about one story."""

    def start(self, story: str) -> typing.Optional[Start]:
        """The story's start as `run --story` decides it; None for an unknown story."""
        ...
