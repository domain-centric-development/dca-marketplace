"""The checkout's one worker: its claim, its release, a listening session's sign of life — each answers with its exit,
already said."""

from __future__ import annotations

import typing

from ....building_blocks import Store


class Checkout(Store, typing.Protocol):
    def freeze_windows(self) -> None:
        """Every story's open windows a finished run left, closed — before anything else writes."""
        ...

    def claim(self, owner: str) -> int:
        """0 where <owner> holds the checkout now, 3 where another does."""
        ...

    def release(self, owner: typing.Optional[str]) -> int:
        """The checkout given back by <owner> (None: this session)."""
        ...

    def listening(self) -> int:
        """This session looked at the backlog."""
        ...
