"""Queue a failed request again."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.request import RequestId, RequestOperation
from ..shared.requests import KIND, RequestFacts, RequestKeeping, RequestRefused, RequestRepository, RequestStore


@dataclasses.dataclass(frozen=True)
class RetryRequestCommand:
    request: str


@dataclasses.dataclass(frozen=True)
class Retried:
    request: RequestFacts


class RetryRequestInputPort(UseCase[RetryRequestCommand, Retried], typing.Protocol):
    """Queue a failed request again."""


class RetryRequestUseCase(RetryRequestInputPort):
    """A failed request queued again, as it was written; any other state is refused."""

    def __init__(self, store: RequestStore, requests: RequestRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary, now: typing.Callable[[], str]) -> None:
        self._store = store
        self._requests = requests
        self._keeping = RequestKeeping(requests, events, transactions)
        self._now = now

    def execute(self, command: RetryRequestCommand) -> Retried:
        request = self._store.find(command.request)
        life = self._requests.get(RequestId(command.request))
        if not life.allows(RequestOperation.RETRY):
            raise RequestRefused(f"{command.request} is {life.state.value} — only a failed request is retried")
        if request.get("kind") not in KIND:
            raise RequestRefused(f"{command.request} cannot be read as a request — drop it")
        life.retry(Moment(self._now()))
        self._keeping.keep(life)
        return Retried(request)
