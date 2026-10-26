"""The checkout's claim and the listener's mark, in the git folder; the open windows frozen first."""

from __future__ import annotations

import typing

from ..files.windows import freeze_all
from .checkout_claim import claim, mark_listening, release, session_owner


class CheckoutFiles:
    def __init__(self, cwd: str, runs: str) -> None:
        self._cwd, self._runs = cwd, runs

    def freeze_windows(self) -> None:
        freeze_all(self._runs)

    def claim(self, owner: str) -> int:
        return claim(self._cwd, owner)

    def release(self, owner: typing.Optional[str]) -> int:
        return release(self._cwd, owner or session_owner())

    def listening(self) -> int:
        return mark_listening(self._cwd)
