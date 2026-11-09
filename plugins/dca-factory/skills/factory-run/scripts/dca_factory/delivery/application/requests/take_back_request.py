"""Take a person's request back."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import TransactionBoundary, UseCase
from ...domain.model.request import RequestId, RequestOperation
from ..shared.requests import RequestFacts, RequestRefused, RequestRepository, RequestStore


@dataclasses.dataclass(frozen=True)
class TakeBackRequestCommand:
    request: str


@dataclasses.dataclass(frozen=True)
class TakenBack:
    request: RequestFacts


class TakeBackRequestInputPort(UseCase[TakeBackRequestCommand, TakenBack], typing.Protocol):
    """Take a request back."""


class TakeBackRequestUseCase(TakeBackRequestInputPort):
    """A request that does not run is removed; one that runs now is the factory's until it ends; the note of a worked
    one is hidden."""

    def __init__(self, store: RequestStore, requests: RequestRepository, transactions: TransactionBoundary) -> None:
        self._store = store
        self._requests = requests
        self._transactions = transactions

    def execute(self, command: TakeBackRequestCommand) -> TakenBack:
        try:
            request = self._store.find(command.request)
        except RequestRefused:
            # a worked request's note: hidden under the wish field, what it made stays in the backlog
            if self._store.hide_done(command.request):
                return TakenBack(dict(id=command.request, state="done"))
            raise
        if not self._requests.get(RequestId(command.request)).allows(RequestOperation.DROP):
            raise RequestRefused(f"{command.request} runs now — it can be dropped once it ended")
        self._transactions.in_transaction(lambda: self._requests.delete_by_id(RequestId(command.request)))
        return TakenBack(request)
