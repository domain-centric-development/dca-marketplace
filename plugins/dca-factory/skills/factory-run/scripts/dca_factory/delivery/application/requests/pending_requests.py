"""The requests not done — written, taken, or asking a person back: what a view's press may be pending on."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.requests import PENDING, Request, RequestStore


@dataclasses.dataclass(frozen=True)
class PendingRequestsQuery:
    pass


@dataclasses.dataclass(frozen=True)
class PendingRequests:
    requests: typing.List[Request]


class PendingRequestsInputPort(UseCase[PendingRequestsQuery, PendingRequests], typing.Protocol):
    """The requests not done."""


class PendingRequestsUseCase:
    """Every request queued, running or waiting, oldest first."""

    def __init__(self, store: RequestStore) -> None:
        self._store = store

    def execute(self, query: PendingRequestsQuery) -> PendingRequests:
        return PendingRequests([r for r in self._store.all() if r["state"] in PENDING])
