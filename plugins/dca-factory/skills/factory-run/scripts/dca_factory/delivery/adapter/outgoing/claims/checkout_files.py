"""The checkout's claim and the listener's mark, in the git folder; the open windows frozen first."""

from __future__ import annotations

import typing

from ..files.windows import freeze_all
from .checkout_claim import claim, mark_listening, release, session_owner
from ..git.checkout import Checkouts
from ....application.shared.checkout import Checkout


class CheckoutFiles(Checkout):
    def __init__(self, cwd: str, runs: str, checkouts: Checkouts) -> None:
        self._cwd, self._runs, self._checkouts = cwd, runs, checkouts

    def freeze_windows(self) -> None:
        freeze_all(self._runs)

    def claim(self, owner: str) -> int:
        return claim(self._cwd, owner, checkouts=self._checkouts)

    def release(self, owner: typing.Optional[str]) -> int:
        return release(self._cwd, owner or session_owner(), self._checkouts)

    def listening(self) -> int:
        return mark_listening(self._cwd, self._checkouts)
