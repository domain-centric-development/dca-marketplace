"""Queue a failed request again."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.requests import KIND, operations_of, Request, RequestRefused, RequestStore


@dataclasses.dataclass(frozen=True)
class RetryRequestCommand:
    request: str


@dataclasses.dataclass(frozen=True)
class Retried:
    request: Request


class RetryRequestInputPort(UseCase[RetryRequestCommand, Retried], typing.Protocol):
    """Queue a failed request again."""


class RetryRequestUseCase:
    """A failed request queued again, as it was written; any other state is refused."""

    def __init__(self, store: RequestStore) -> None:
        self._store = store

    def execute(self, command: RetryRequestCommand) -> Retried:
        request = self._store.find(command.request)
        if "retry" not in operations_of(request["state"]):
            raise RequestRefused(f"{command.request} is {request['state']} — only a failed request is retried")
        if request.get("kind") not in KIND:
            raise RequestRefused(f"{command.request} cannot be read as a request — drop it")
        self._store.update(request, state="queued", error=None, worker=None, started=None)
        return Retried(request)
