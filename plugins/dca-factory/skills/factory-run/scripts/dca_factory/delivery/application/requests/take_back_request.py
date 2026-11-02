"""Take a person's request back."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.requests import operations_of, Request, RequestRefused, RequestStore


@dataclasses.dataclass(frozen=True)
class TakeBackRequestCommand:
    request: str


@dataclasses.dataclass(frozen=True)
class TakenBack:
    request: Request


class TakeBackRequestInputPort(UseCase[TakeBackRequestCommand, TakenBack], typing.Protocol):
    """Take a request back."""


class TakeBackRequestUseCase:
    """A request that does not run is removed; one that runs now is the factory's until it ends; the note of a worked
    one is hidden."""

    def __init__(self, store: RequestStore) -> None:
        self._store = store

    def execute(self, command: TakeBackRequestCommand) -> TakenBack:
        try:
            request = self._store.find(command.request)
        except RequestRefused:
            # a worked request's note: hidden under the wish field, what it made stays in the backlog
            if self._store.hide_done(command.request):
                return TakenBack(dict(id=command.request, state="done"))
            raise
        if "drop" not in operations_of(request["state"]):
            raise RequestRefused(f"{command.request} runs now — it can be dropped once it ended")
        self._store.remove(request)
        return TakenBack(request)
