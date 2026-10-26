"""Work one request: its skill run headless with the request as the person's confirmation, or settled by the factory
itself, and what it wrote committed as the backlog's."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.backlog_changes import BacklogChanges
from ..shared.request_records import RequestRecords
from ..shared.request_settlement import RequestSettlement
from ..shared.request_skill import RequestSkill
from ..shared.requests import Kind, KIND, Request, RequestRefused, RequestStore, written_keys
from .list_requests import target_text
from ...domain.model.decision_record import WAITING_WORDS

#: (stream, line): what the factory says on its way — `out` for the person, `err` for a refusal or a failure
Said = typing.List[typing.Tuple[str, str]]


@dataclasses.dataclass(frozen=True)
class WorkRequestCommand:
    """The request, the tool the run was given, and the worker that works it."""

    request: str
    tool: str
    worker: str


@dataclasses.dataclass(frozen=True)
class RequestWorked:
    """0 done (and gone), 3 a person is asked (waiting), 1 failed (kept, `error:`); what was said on the way; the
    commit of what it wrote, "" where there is none."""

    code: int
    said: Said
    commit: str = ""


class WorkRequestInputPort(UseCase[WorkRequestCommand, RequestWorked], typing.Protocol):
    """Work one request."""


class WorkRequestUseCase:
    """A request whose skill did its part and whose commit was refused commits what it wrote and runs no skill again;
    one that no longer holds fails; one the factory settles itself is settled; any other runs its skill. A skill that
    asks a person leaves the request waiting; its question and what it wrote are committed — the backlog and the
    description only, never code and never what a person had changed before."""

    def __init__(self, store: RequestStore, records: RequestRecords, changes: BacklogChanges, skill: RequestSkill,
                 settlement: RequestSettlement, now: typing.Callable[[], str]) -> None:
        self._store = store
        self._records = records
        self._changes = changes
        self._skill = skill
        self._settlement = settlement
        self._now = now

    def execute(self, command: WorkRequestCommand) -> RequestWorked:
        said: Said = []
        try:
            request = self._store.find(command.request)
        except RequestRefused as error:
            return RequestWorked(1, [("err", f"factory: {error}")])
        if request["state"] != "queued":
            return RequestWorked(0, [("out", f"factory: request {command.request} is {request['state']} — nothing to do")])
        kind = KIND[request["kind"]]
        if not kind.skill:
            self._store.update(request, state="failed", error=f"a {kind.name} request is the runner's, no skill works it")
            return RequestWorked(1, said)
        if request.get("worked"):
            return self._commit_worked(request, kind)
        # what held when it was written may not hold now — an answer given by hand, a story released meanwhile. A
        # request resumed after its own question is past that: what its first run did (an answer written, an
        # acceptance taken) is why its record no longer reads open, so it is not checked again.
        if not request.get("answered"):
            try:
                self._settlement.holds(kind, {k: request[k] for k in written_keys(kind) if request.get(k)},
                                       request.get("words", ""))
            except RequestRefused as error:
                self._store.update(request, state="failed", error=f"no longer holds — {error}")
                self._store.journal("request-end", kind.name, request["id"], "exit=1", "state=failed", str(error))
                return RequestWorked(1, [("err", f"factory: request {request['id']} no longer holds — {error}")])
            settled = self.settle(request, kind)
            if settled is not None:
                return settled
        unit = f"request:{kind.name}"
        tool = self._skill.tool_for(unit, command.tool)
        if not self._skill.known(tool):
            self._store.update(request, state="failed", error=f"no known tool {tool!r} to run it with")
            return RequestWorked(1, said)
        attempts = int(request.get("attempts") or 0) + 1
        self._store.update(request, state="running", worker=command.worker, started=self._now(),
                           attempts=str(attempts), error=None)
        self._store.journal("request-start", kind.name, request["id"], target_text(request),
                            f"by={request.get('by', '')}", f"tool={tool}", f"attempt={attempts}")
        before = self._changes.dirty()
        try:
            ran = self._skill.run(request, kind, unit, tool)
        except BaseException:
            self._store.update(request, state="queued", worker=None, started=None,
                               wrote=self._wrote(request, before))
            self._store.journal("request-end", kind.name, request["id"], "exit=stopped", "state=queued")
            raise
        if ran.code != 0:
            why = "ran past its time limit" if ran.timed_out else f"ended with exit {ran.code}"
            self._store.update(request, state="failed", worker=None, wrote=self._wrote(request, before),
                               error=f"the tool {why} — its output: {ran.output}")
            self._store.journal("request-end", kind.name, request["id"], f"exit={ran.code}", "state=failed")
            return RequestWorked(1, [("err", f"factory: request {request['id']} — the tool {why}; it stays as failed "
                                             f"(`factory.sh requests`).")])
        asked = [(where, rid) for where, rid, state in self._records.asked(request["id"]) if state in WAITING_WORDS]
        if asked:
            commit, refusal = self._commit(request, before, said)
            self._store.update(request, state="waiting", worker=None, record_file=asked[0][0],
                               wrote=self._wrote(request, before) if refusal else None)
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=waiting",
                                f"record={asked[0][1]}", f"commit={commit or '-'}")
            said.append(("out", f"factory: request {request['id']} asks a person — {asked[0][0]}; it runs again once "
                                f"answered."))
            return RequestWorked(3, said, commit)
        self._records.applied(request["id"])
        if kind.name in ("wish", "stories"):
            self._records.questioned(self._wrote(request, before).split(), request["id"])
        # gone before its commit: a crash between the two leaves what it wrote uncommitted — never a request that
        # would run its skill a second time
        self._remove(request)
        commit, refusal = self._commit(request, before, said)
        if refusal:
            # its skill did its part; what it wrote waits in the checkout for a person, as the failed request says —
            # and its retry commits it, never running the skill again (`worked:`)
            self._store.update(request, restore=True, state="failed", worker=None, error=refusal,
                               wrote=self._wrote(request, before), worked=self._now())
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return RequestWorked(1, said)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit or '-'}")
        said.append(("out", f"factory: request {request['id']} done"
                            + (f" — committed {commit}" if commit else " — nothing to commit")))
        return RequestWorked(0, said, commit)

    def settle(self, request: Request, kind: Kind) -> typing.Optional[RequestWorked]:
        """A request the factory settles itself: written and committed at once, no tool started. None where a skill
        must work it. A request settled on a press has no file: nothing to keep or remove."""
        said: Said = []
        before = self._changes.dirty()
        try:
            wrote = self._settlement.settle(request, self._now())
        except RequestRefused as error:
            if request.get("path"):
                self._store.update(request, state="failed", error=f"no longer holds — {error}")
            self._store.journal("request-end", kind.name, request["id"], "exit=1", "state=failed", str(error))
            return RequestWorked(1, [("err", f"factory: request {request['id']} no longer holds — {error}")])
        if wrote is None:
            return None
        self._store.journal("request-start", kind.name, request["id"], target_text(request),
                            f"by={request.get('by', '')}", "tool=factory", "attempt=1")
        if request.get("path"):
            self._remove(request)
        commit, refusal = self._commit(request, before, said)
        if refusal:
            if request.get("path"):
                self._store.update(request, restore=True, state="failed", worker=None, error=refusal,
                                   wrote=self._wrote(request, before), worked=self._now())
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return RequestWorked(1, said, commit)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", "by=factory",
                            f"commit={commit or '-'}")
        said.append(("out", f"factory: request {request['id']} settled by the factory, no tool"
                            + (f" — committed {commit}" if commit else "")))
        return RequestWorked(0, said, commit)

    def _commit_worked(self, request: Request, kind: Kind) -> RequestWorked:
        """A request whose skill did its part and whose commit was refused, queued again: what it wrote is committed —
        the skill is not run again, and what it wrote is not checked as a new request (an answer it wrote reads as
        answered by now). Refused again, it stays failed with the reason."""
        said: Said = []
        commit, refusal = self._commit(request, self._changes.dirty(), said)
        if refusal or not commit:
            why = refusal or "nothing it wrote is left in the checkout to commit"
            self._store.update(request, state="failed", worker=None, error=why)
            self._store.journal("request-end", kind.name, request["id"], "exit=1", "state=failed", "commit=refused")
            said.append(("err", f"factory: request {request['id']}: {why}"))
            return RequestWorked(1, said)
        self._remove(request)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit}")
        said.append(("out", f"factory: request {request['id']} done — committed {commit}"))
        return RequestWorked(0, said, commit)

    def _remove(self, request: Request) -> None:
        try:
            self._store.remove(request)
        except OSError:
            pass

    def _wrote(self, request: Request, before: typing.Mapping[str, str]) -> str:
        """What a request wrote so far — the people's paths it changed that were clean before, and what an earlier
        attempt of it wrote —, kept in its file when it fails or is interrupted: an attempt after it commits them as
        its own, never as a person's."""
        after = self._changes.dirty()
        new = {p for p, digest in after.items() if before.get(p) != digest and p not in before}
        own = set(str(request.get("wrote") or "").split())
        return " ".join(sorted(self._changes.people((new | own) & set(after))))

    def _commit(self, request: Request, before: typing.Mapping[str, str], said: Said) -> typing.Tuple[str, str]:
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
