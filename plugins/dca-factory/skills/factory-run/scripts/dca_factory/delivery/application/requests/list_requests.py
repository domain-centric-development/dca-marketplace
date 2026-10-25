"""List the requests: every one with its state, oldest first — the order the factory works them in."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.requests import KINDS, operations_of, Request, RequestStore, STATES

#: The word on a request's button for each operation.
OPERATION_LABELS = {"follow": "follow", "retry": "retry", "drop": "take back"}


@dataclasses.dataclass(frozen=True)
class ListRequestsQuery:
    pass


#: The view's model: `requests` (rows), `counts` by state, `counts_text`, the `kinds` a request can be, the `store`.
RequestList = typing.Dict[str, typing.Any]


class ListRequestsInputPort(UseCase[ListRequestsQuery, RequestList], typing.Protocol):
    """List the requests."""


class ListRequestsUseCase:
    """`factory.sh requests`, the page's request view: each request with what a person can do with it."""

    def __init__(self, store: RequestStore) -> None:
        self._store = store

    def execute(self, query: ListRequestsQuery) -> RequestList:
        rows = []
        for request in self._store.all():
            rows.append(dict(id=request["id"], kind=request.get("kind", "?"), state=request["state"],
                             target=target_text(request), by=request.get("by", ""), asked=request.get("asked", ""),
                             worker=request.get("worker", ""), started=request.get("started", ""),
                             record=request.get("record_file", ""), error=request.get("error", ""),
                             words=request.get("words", ""), option=request.get("option", ""),
                             story=request.get("story", ""), epic=request.get("epic", ""),
                             path=self._store.shown(request),
                             operations=[dict(name=o, label=OPERATION_LABELS[o]) for o in operations_of(request["state"])]))
        counted = {s: sum(r["state"] == s for r in rows) for s in STATES}
        return dict(requests=rows, counts=counted,
                    counts_text=", ".join(f"{n} {'asking' if s == 'waiting' else s}" for s, n in counted.items() if n),
                    kinds=[dict(kind=k.name, keys=list(k.keys), words=k.words, option=k.option, about=k.about)
                           for k in KINDS],
                    store=self._store.where() + "/")


def target_text(request: Request) -> str:
    """What a request is about, as one short phrase."""
    for key in ("record", "story", "epic"):
        if request.get(key):
            return str(request[key])
    if request.get("proposal"):
        return f"{request.get('topic')}/{request['proposal']}"
    words = " ".join(str(request.get("words", "")).split())
    return (words[:60] + "…") if len(words) > 60 else words
