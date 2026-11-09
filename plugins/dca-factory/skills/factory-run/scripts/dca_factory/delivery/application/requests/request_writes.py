"""What a request wrote, kept apart from what a person wrote: the people's paths it changed, committed on their own —
shared by the use cases that work and settle a request."""

from __future__ import annotations

import typing

from ..shared.backlog_changes import BacklogChanges
from ..shared.requests import RequestFacts, RequestRepository
from ...domain.model.request import RequestId
from .request_worked import Said
from .list_requests import target_text


class RequestWrites:
    """The writes of one request in the checkout <changes>, its file in <requests>."""

    def __init__(self, requests: RequestRepository, changes: BacklogChanges) -> None:
        self._requests = requests
        self._changes = changes

    def remove(self, request: RequestFacts) -> None:
        """Its file gone before its commit: a crash between the two leaves what it wrote uncommitted — never a request
        that would run its skill a second time. A refused commit writes it back (the repository took it away)."""
        try:
            self._requests.delete_by_id(RequestId(request["id"]))
        except OSError:
            pass

    def wrote(self, request: RequestFacts, before: typing.Mapping[str, str]) -> str:
        """What a request wrote so far — the people's paths it changed that were clean before, and what an earlier
        attempt of it wrote —, kept in its file when it fails or is interrupted: an attempt after it commits them as
        its own, never as a person's."""
        after = self._changes.dirty()
        new = {p for p, digest in after.items() if before.get(p) != digest and p not in before}
        own = set(str(request.get("wrote") or "").split())
        return " ".join(sorted(self._changes.people((new | own) & set(after))))

    def commit(self, request: RequestFacts, before: typing.Mapping[str, str], said: Said) -> typing.Tuple[str, str]:
        """What the request wrote, committed on its own: the paths it changed that were clean before — or that an
        earlier attempt of it wrote (`wrote:`) — and that are the backlog or the description. A path a person had
        changed before, or code, stays as it is and is named. (commit, why it was refused)"""
        after = self._changes.dirty()
        own = set(str(request.get("wrote") or "").split())
        changed = sorted(p for p, digest in after.items() if before.get(p) != digest or p in own)
        people = self._changes.people(changed)
        mine = [p for p in changed if (p not in before or p in own) and p in people]
        theirs = [p for p in changed if p in before and p not in own]
        stray = [p for p in changed if p not in before and p not in mine]
        if theirs:
            said.append(("out", f"factory: request {request['id']} changed what was changed by hand before — left "
                                f"uncommitted: {', '.join(theirs[:8])}"))
        if stray:
            said.append(("err", f"factory: request {request['id']} changed what is neither backlog nor description "
                                f"(code, the spec) — left uncommitted: {', '.join(stray[:8])}"))
        if not mine:
            return "", ""
        message = (f"chore(backlog): {request['kind']} {target_text(request)}\n\nRequest: {request['id']}\n"
                   f"By: {request.get('by', '')}\n")
        committed = self._changes.commit(mine, message)
        if committed.refusal:
            refusal = f"what it wrote could not be committed — {committed.refusal}"
            said.append(("err", f"factory: request {request['id']}: {refusal}; it stays in the checkout, unstaged"))
            return "", refusal
        return committed.head, ""
