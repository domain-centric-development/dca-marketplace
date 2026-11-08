"""The checkout feature's commands of the cli: a session listening, the checkout taken and given back."""

from __future__ import annotations

import typing

from ....application.checkout.give_checkout_back import GiveCheckoutBackCommand
from ....application.checkout.mark_listening import MarkListeningCommand
from ....application.checkout.take_checkout import TakeCheckoutCommand
from . import root


def mark_listening(cwd: str, runs: str) -> int:
    return root.wiring.mark_listening(cwd, runs).execute(MarkListeningCommand())


def take_checkout(cwd: str, runs: str, owner: str) -> int:
    return root.wiring.take_checkout(cwd, runs).execute(TakeCheckoutCommand(owner))


def give_checkout_back(cwd: str, runs: str, owner: typing.Optional[str]) -> int:
    return root.wiring.give_checkout_back(cwd, runs).execute(GiveCheckoutBackCommand(owner))
