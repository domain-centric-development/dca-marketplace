"""Work one request: its skill run headless with the request as the person's confirmation, or settled by the factory
itself, and what it wrote committed as the backlog's."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.backlog_changes import BacklogChanges
from ..shared.request_records import RequestRecords
from ..shared.request_settlement import RequestSettlement
from ..shared.handed_file_store import HandedFileStore
from ..shared.request_skill import HandedFileRead, RequestSkill
from ..shared.requests import (Kind, KIND, Request, RequestRefused, RequestStore, named_files,
                               written_keys)
from .list_requests import target_text
from ...domain.model.decision_record import WAITING_WORDS
from ..delivery.pipeline_rules import decides
from .request_writes import RequestWrites
from .request_worked import RequestWorked as RequestWorked, Said as Said
from .settle_request import RequestSettling



@dataclasses.dataclass(frozen=True)
class WorkRequestCommand:
    """The request, the tool the run was given, and the worker that works it."""

    request: str
    tool: str
    worker: str




class WorkRequestInputPort(UseCase[WorkRequestCommand, RequestWorked], typing.Protocol):
    """Work one request."""


class WorkRequestUseCase(WorkRequestInputPort):
    """A request whose skill did its part and whose commit was refused commits what it wrote and runs no skill again;
    one that no longer holds fails; one the factory settles itself is settled; any other runs its skill. A skill that
    asks a person leaves the request waiting; its question and what it wrote are committed — the backlog and the
    description only, never code and never what a person had changed before."""

    def __init__(self, store: RequestStore, records: RequestRecords, changes: BacklogChanges, skill: RequestSkill,
                 settlement: RequestSettlement, now: typing.Callable[[], str], files: HandedFileStore) -> None:
        self._store = store
        self._settling = RequestSettling(store, changes, settlement, now)
        self._writes = RequestWrites(store, changes)
        self._files = files
        self._records = records
        self._changes = changes
        self._skill = skill
        self._settlement = settlement
        self._now = now

    @decides(
        "RUN-REQUEST-4",
    )
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
            settled = self._settling.settle(request, kind)
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
            ran = self._skill.run(request, kind, unit, tool, self._handed(request))
        except BaseException:
            self._store.update(request, state="queued", worker=None, started=None,
                               wrote=self._writes.wrote(request, before))
            self._store.journal("request-end", kind.name, request["id"], "exit=stopped", "state=queued")
            raise
        # the files no live request names any more go, once older than the domain keeps them (WP-184)
        self._files.prune(named_files(self._store.all()))
        if ran.code != 0:
            why = "ran past its time limit" if ran.timed_out else f"ended with exit {ran.code}"
            self._store.update(request, state="failed", worker=None, wrote=self._writes.wrote(request, before),
                               error=f"the tool {why} — its output: {ran.output}")
            self._store.journal("request-end", kind.name, request["id"], f"exit={ran.code}", "state=failed")
            return RequestWorked(1, [("err", f"factory: request {request['id']} — the tool {why}; it stays as failed "
                                             f"(`factory.sh requests`).")])
        asked = [(where, rid) for where, rid, state in self._records.asked(request["id"]) if state in WAITING_WORDS]
        if asked:
            commit, refusal = self._writes.commit(request, before, said)
            self._store.update(request, state="waiting", worker=None, record_file=asked[0][0],
                               wrote=self._writes.wrote(request, before) if refusal else None)
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=waiting",
                                f"record={asked[0][1]}", f"commit={commit or '-'}")
            said.append(("out", f"factory: request {request['id']} asks a person — {asked[0][0]}; it runs again once "
                                f"answered."))
            return RequestWorked(3, said, commit)
        self._records.applied(request["id"])
        wrote = self._writes.wrote(request, before)
        if kind.name in ("wish", "stories"):
            self._records.questioned(wrote.split(), request["id"])
        # gone before its commit: a crash between the two leaves what it wrote uncommitted — never a request that
        # would run its skill a second time
        self._writes.remove(request)
        commit, refusal = self._writes.commit(request, before, said)
        if refusal:
            # its skill did its part; what it wrote waits in the checkout for a person, as the failed request says —
            # and its retry commits it, never running the skill again (`worked:`)
            self._store.update(request, restore=True, state="failed", worker=None, error=refusal,
                               wrote=self._writes.wrote(request, before), worked=self._now())
            self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return RequestWorked(1, said)
        self._keep(request, kind, wrote, commit)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit or '-'}")
        said.append(("out", f"factory: request {request['id']} done"
                            + (f" — committed {commit}" if commit else " — nothing to commit")))
        return RequestWorked(0, said, commit)


    def _commit_worked(self, request: Request, kind: Kind) -> RequestWorked:
        """A request whose skill did its part and whose commit was refused, queued again: what it wrote is committed —
        the skill is not run again, and what it wrote is not checked as a new request (an answer it wrote reads as
        answered by now). Refused again, it stays failed with the reason."""
        said: Said = []
        commit, refusal = self._writes.commit(request, self._changes.dirty(), said)
        if refusal or not commit:
            why = refusal or "nothing it wrote is left in the checkout to commit"
            self._store.update(request, state="failed", worker=None, error=why)
            self._store.journal("request-end", kind.name, request["id"], "exit=1", "state=failed", "commit=refused")
            said.append(("err", f"factory: request {request['id']}: {why}"))
            return RequestWorked(1, said)
        self._writes.remove(request)
        self._keep(request, kind, str(request.get("wrote") or ""), commit)
        self._store.journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit}")
        said.append(("out", f"factory: request {request['id']} done — committed {commit}"))
        return RequestWorked(0, said, commit)

    def _handed(self, request: Request) -> typing.List[HandedFileRead]:
        """The files the request names that are still kept, each where its run reads it."""
        handed = []
        for file_id in named_files([request]):
            ref, path = self._files.find(file_id), self._files.readable(file_id)
            if ref and path:
                handed.append(HandedFileRead(ref, path))
        return handed

    def _keep(self, request: Request, kind: Kind, wrote: str, commit: str) -> None:
        """A request that has an agent write something new leaves a note of what it made, for the person who asked."""
        if kind.creates:
            try:
                self._store.keep_done(request, wrote, commit, self._now())
            except OSError:
                pass



