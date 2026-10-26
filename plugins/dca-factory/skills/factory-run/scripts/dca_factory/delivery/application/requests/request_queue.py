"""The runner's queue of requests: which one it works next, which it takes itself (`run`, `stop`), and what becomes of
one whose process ended without saying how."""

from __future__ import annotations

import dataclasses
import typing

from ..shared.request_records import RequestRecords
from ..shared.requests import KIND, Request, RequestRefused, RequestStore, stories_of
from ..shared.run_lines import RunLines
from ..shared.story_starts import StoryStarts
from ...domain.model.decision_record import ANSWERED_WORDS

#: The exits of a request's process that end it with no word of its own: a hang-up, an interrupt, a TERM.
STOPPED_EXITS = (129, 130, 143)


@dataclasses.dataclass(frozen=True)
class RunAsked:
    """A `run` request taken: its story starts next, from `start`; `named` when the request named the stage."""

    request: Request
    start: str
    named: bool


class RequestQueue:
    """The requests as the runner holding the claim works them: before the next story, between the stages of a running
    one, and in a slot of its own in a parallel run — oldest first."""

    def __init__(self, store: RequestStore, records: RequestRecords, starts: StoryStarts, worker: str,
                 lines: RunLines) -> None:
        self._store = store
        self._records = records
        self._starts = starts
        self._worker = worker
        self._lines = lines

    def requeue_orphans(self) -> None:
        """A request a factory left `running` when it ended — crashed, killed — is queued again: this runner holds the
        claim now, so nobody else works it."""
        for request in self._store.all():
            if request["state"] == "running" and request.get("worker") != self._worker:
                self._store.update(request, state="queued", worker=None, started=None)
                self._lines.out(f"factory: request {request['id']} was left running by "
                                f"{request.get('worker') or 'a factory'} — queued again")

    def wake_waiting(self) -> None:
        """A waiting request whose records are all answered is queued again, with the answers to read."""
        for request in self._store.all():
            if request["state"] != "waiting":
                continue
            records = self._records.asked(request["id"])
            if not records:                     # its record was removed by hand: it runs again and asks again
                self._store.update(request, state="queued", record_file=None)
                self._lines.out(f"factory: request {request['id']} waited on a record that is gone — it runs again")
                continue
            if all(state in ANSWERED_WORDS for _p, _id, state in records):
                self._store.update(request, state="queued", record_file=None,
                                   answered=" ".join(rid for _p, rid, _s in records))
                self._lines.out(f"factory: request {request['id']} — its question is answered; it runs again")

    def next(self, busy: typing.Iterable[str] = (),
             kinds: typing.Optional[typing.Sequence[str]] = None) -> typing.Optional[Request]:
        """The oldest queued request this runner may work now: of the kinds given (else every kind a skill works), and
        about no story in <busy>."""
        self.wake_waiting()
        busy = set(busy)
        for request in self._store.all():
            if request["state"] != "queued" or request.get("kind") not in KIND:
                continue
            kind = KIND[request["kind"]]
            if (kinds is not None and kind.name not in kinds) or (kinds is None and not kind.skill):
                continue
            if stories_of(request) & busy:
                continue
            return request
        return None

    def any_queued(self) -> bool:
        return any(request["state"] == "queued" for request in self._store.all())

    def take_stop(self) -> bool:
        """A `stop` request ends this factory after the running stage: taken, journaled, gone. True when there was one."""
        request = self.next(kinds=("stop",))
        if not request:
            return False
        self._store.remove(request)
        self._store.journal("request", "stop", request["id"], "-", f"by={request.get('by', '')}", "exit=0")
        self._lines.out(f"factory: request {request['id']} — {request.get('by') or 'a person'} stops the factory; "
                        "nothing more starts.")
        return True

    def take_run(self, busy: typing.Iterable[str] = ()) -> typing.Optional[RunAsked]:
        """The oldest `run` request whose story is not running — its story starts next — or a failed request said and
        set aside. None when there is none."""
        while True:
            request = self.next(busy, kinds=("run",))
            if not request:
                return None
            start, why = self._start_of(request)
            if start:
                self._store.remove(request)
                self._store.journal("request", "run", request["id"], request["story"], f"by={request.get('by', '')}",
                                    f"from={start}")
                self._lines.out(f"factory: request {request['id']} — {request.get('by') or 'a person'} runs "
                                f"{request['story']} from {start} now")
                return RunAsked(request, start, bool(request.get("from")))
            self._store.update(request, state="failed", error=f"nothing runs: {why}")
            self._store.journal("request", "run", request["id"], request["story"], f"by={request.get('by', '')}",
                                "exit=1", why)
            self._lines.err(f"factory: request {request['id']} — {why}; nothing runs.")

    def run_ended(self, request: Request, code: int) -> None:
        """A `run` request's story ended: the journal says how."""
        self._store.journal("request-end", "run", request["id"], f"exit={code}")

    def ended(self, request: Request, code: int) -> None:
        """After a request's process: one that ended without saying how — killed, a crash before its first line — is
        failed, so it is never taken again on its own; one stopped by a signal is queued for the next start."""
        if code in (0, 3):
            return
        try:
            now = self._store.find(request["id"])
        except RequestRefused:
            now = None
        if now is not None and now["state"] in ("queued", "running"):
            if code in STOPPED_EXITS or code < 0:
                self._store.update(now, state="queued", worker=None, started=None)
                self._lines.err(f"factory: request {request['id']} was stopped — queued again for the next start.")
                return
            self._store.update(now, state="failed", worker=None,
                               error=f"its process ended with exit {code} before it said how")
        self._lines.err(f"factory: request {request['id']} ended with exit {code} — `factory.sh requests` says why; "
                        "the factory goes on.")

    def _start_of(self, request: Request) -> typing.Tuple[typing.Optional[str], str]:
        """(start stage or None, why not) — where a `run` request's story begins: the stage it names, else where its
        files say, as `run --story` decides it."""
        story, start = request["story"], request.get("from", "")
        if start:
            return start, ""
        found = self._starts.start(story)
        if found is None:
            return None, f"no story {story}"
        state, stage, detail = found
        if not stage:
            return None, f"{story} is {state}" + (f" — {detail}" if detail else "")
        return stage, ""
