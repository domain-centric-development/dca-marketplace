"""List the requests: every one with its state, oldest first — the order the factory works them in."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.requests import KINDS, MadeItems, operations_of, place_of, Request, RequestStore, STATES
from ..status.actions import make_action

#: The word on a request's button for each operation.
OPERATION_LABELS = {"follow": "follow", "retry": "retry", "drop": "take back"}


@dataclasses.dataclass(frozen=True)
class ListRequestsQuery:
    pass


#: The view's model: `requests` (rows), `counts` by state, `counts_text`, the `kinds` a request can be, the `store`,
#: and `wishes` — the trail under a wish field: every wish, newest first, with what became of it.
RequestList = typing.Dict[str, typing.Any]


class ListRequestsInputPort(UseCase[ListRequestsQuery, RequestList], typing.Protocol):
    """List the requests."""


class ListRequestsUseCase:
    """`factory.sh requests`, the page's request view: each request with what a person can do with it, and the trail of
    the wishes — one waiting, writing, asking back or failed, and one done until what it made is released or hidden."""

    def __init__(self, store: RequestStore, made: typing.Optional[MadeItems] = None) -> None:
        self._store = store
        self._made = made

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
                    store=self._store.where() + "/", wishes=self._wishes())

    def _wishes(self) -> typing.List[typing.Dict[str, typing.Any]]:
        trail = [wish_entry(r, []) for r in self._store.all() if r.get("kind") == "wish"]
        if self._made is not None:
            for note in self._store.done():
                if note.get("kind") != "wish":
                    continue
                made = self._made.at(str(note.get("wrote") or "").split())
                drafts = [m for m in made if m["status"] == "draft"]
                if made and not drafts:
                    continue                          # released: it lives in the backlog now, not under the field
                trail.append(wish_entry(note, drafts))
        return sorted(trail, key=lambda w: w["asked"], reverse=True)


def wish_entry(request: Request, drafts: typing.List[typing.Dict[str, str]]) -> typing.Dict[str, typing.Any]:
    """One wish as its trail shows it: its words, who and when, its state in words and what a person can do there."""
    state = request["state"]
    first = drafts[0] if drafts else None
    if state == "done":
        text = (f"became a draft {first['kind']}: {first['title']}" + (f" — and {len(drafts) - 1} more" if len(drafts) > 1
                else "")) if first else "wrote nothing new"
    else:
        text = {"queued": "waits its turn", "running": "writing",
                "waiting": f"asks you back — answer it on {place_of(request['id'])}"}.get(state) \
            or " ".join(str(request.get("error") or "failed").split())[:160]
    release = [make_action(lambda word: True, skill=f"/factory-backlog release {d['id']}", label="release",
                           primary=True) for d in drafts[:1]]
    return dict(id=request["id"], words=str(request.get("words") or ""), by=str(request.get("by") or ""),
                asked=str(request.get("asked") or ""), started=str(request.get("started") or ""), state=state,
                tone={"done": "ok", "waiting": "ask", "failed": "bad"}.get(state, "wait"), text=text,
                place=place_of(request["id"]), made=drafts, actions=release,
                files=len(str(request.get("files") or "").split()),        # handed over beside the words (WP-184)
                operations=[dict(name="hide", label="✕")] if state == "done"
                else [dict(name=o, label=OPERATION_LABELS[o]) for o in operations_of(state) if o != "follow"])


def target_text(request: Request) -> str:
    """What a request is about, as one short phrase."""
    for key in ("record", "story", "epic"):
        if request.get(key):
            return str(request[key])
    if request.get("proposal"):
        return f"{request.get('topic')}/{request['proposal']}"
    if request.get("topic"):
        return f"{request['topic']}: " + " ".join(str(request.get("words", "")).split())[:50]
    words = " ".join(str(request.get("words", "")).split())
    return (words[:60] + "…") if len(words) > 60 else words
