"""Settle a request the factory works itself: written and committed at once, no tool started."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.request import Request, RequestId, Why
from ..shared.backlog_changes import BacklogChanges
from ..shared.request_settlement import RequestSettlement
from ..shared.requests import (Kind, paths, RequestFacts, RequestKeeping, RequestRefused, RequestRepository,
                               RequestStore)
from .list_requests import target_text
from .request_writes import RequestWrites
from .request_worked import RequestWorked, Said


@dataclasses.dataclass(frozen=True)
class SettleRequestCommand:
    request: RequestFacts
    kind: Kind


class SettleRequestInputPort(UseCase[SettleRequestCommand, typing.Optional[RequestWorked]], typing.Protocol):
    """Settle a request: what settling it said — None where a skill must work it."""


class RequestSettling:
    """A request the factory settles itself: written and committed at once, no tool started. A request settled on a
    press has no file: nothing to keep or remove."""

    def __init__(self, store: RequestStore, changes: BacklogChanges, settlement: RequestSettlement,
                 now: typing.Callable[[], str], *, requests: RequestRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._store = store
        self._requests = requests
        self._keeping = RequestKeeping(requests, events, transactions)
        self._changes = changes
        self._settlement = settlement
        self._now = now
        self._writes = RequestWrites(requests, changes)

    def settle(self, request: RequestFacts, kind: Kind,
               life: typing.Optional[Request] = None) -> typing.Optional[RequestWorked]:
        """A request the factory settles itself: written and committed at once, no tool started. None where a skill
        must work it. A request settled on a press has no file: nothing to keep or remove — <life> is the aggregate
        of one that has, read here where the caller holds none."""
        said: Said = []
        if life is None and request.get("path"):
            life = self._requests.get(RequestId(request["id"]))
        before = self._changes.dirty()
        try:
            wrote = self._settlement.settle(request, self._now())
        except RequestRefused as error:
            if life is not None:
                life.fail(Why(f"no longer holds — {error}"), self._at())
                self._keeping.keep(life)
            self._store.journal("request-end", kind.name, request["id"], "exit=1", "state=failed", str(error))
            return RequestWorked(1, [("err", f"factory: request {request['id']} no longer holds — {error}")])
        if wrote is None:
            return None
        self._store.journal("request-start", kind.name, request["id"], target_text(request),
                            f"by={request.get('by', '')}", "tool=factory", "attempt=1")
        if request.get("path"):
            self._writes.remove(request)
        commit, refusal = self._writes.commit(request, before, said)
        if refusal:
            if life is not None:
                life.leave_uncommitted(Why(refusal), paths(self._writes.wrote(request, before)), self._at())
                self._keeping.keep(life)
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return RequestWorked(1, said, commit)
        if life is not None:
            life.settle(self._at())
            self._keeping.keep(life)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", "by=factory",
                            f"commit={commit or '-'}")
        said.append(("out", f"factory: request {request['id']} settled by the factory, no tool"
                            + (f" — committed {commit}" if commit else "")))
        return RequestWorked(0, said, commit)


    def _at(self) -> Moment:
        return Moment(self._now())


class SettleRequestUseCase(SettleRequestInputPort):
    """Settle one request (`RequestSettling`)."""

    def __init__(self, store: RequestStore, changes: BacklogChanges, settlement: RequestSettlement,
                 now: typing.Callable[[], str], *, requests: RequestRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._settling = RequestSettling(store, changes, settlement, now, requests=requests, events=events,
                                         transactions=transactions)

    def execute(self, command: SettleRequestCommand) -> typing.Optional[RequestWorked]:
        return self._settling.settle(command.request, command.kind)
