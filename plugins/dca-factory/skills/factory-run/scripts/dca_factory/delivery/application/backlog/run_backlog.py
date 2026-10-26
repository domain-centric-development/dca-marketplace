"""Run the backlog: story after story in the order the schedule names, read off the files every time — one at a time,
or several side by side, each in its worktree — with a person's requests before the next story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..requests.request_queue import RequestQueue, RunAsked
from ..shared.backlog_schedule import BacklogSchedule, ScheduleRead
from ..shared.backlog_worker import BacklogCheckout, BacklogWorker, Child
from ..shared.requests import Request, stories_of
from ..shared.run_lines import RunLines


@dataclasses.dataclass(frozen=True)
class RunBacklogCommand:
    slots: int                  #: how many stories run at once
    watch: bool = False         #: wait for a released story or an answer once nothing can run
    interval: int = 60          #: the watch's pause, in seconds
    dry: bool = False           #: name the first story and what would run, start nothing
    keep_going: bool = False    #: a stopped story is set aside with what depends on it; the run goes on
    stay: bool = False          #: the watch waits even when nothing waits on an answer


class RunBacklogInputPort(UseCase[RunBacklogCommand, int], typing.Protocol):
    """Run the backlog: its exit."""


class RunBacklogUseCase:
    """The backlog run: 0 once nothing more can start, the exit of the first story that stopped it, 5 when another
    worker took the checkout over. With --keep-going a stopped story is skipped with what depends on it, unless the
    stop concerns the whole run."""

    def __init__(self, schedule: BacklogSchedule, checkout: BacklogCheckout, worker: BacklogWorker,
                 queue: RequestQueue, lines: RunLines) -> None:
        self._schedule = schedule
        self._checkout = checkout
        self._worker = worker
        self._queue = queue
        self._lines = lines
        self._skipped: typing.Dict[str, int] = {}

    def execute(self, command: RunBacklogCommand) -> int:
        self._skipped = {}
        if not command.dry:
            self._checkout.prune()
            self._queue.requeue_orphans()
        if command.slots > 1 and not command.dry:
            return self._side_by_side(command)
        return self._one_at_a_time(command)

    def _one_at_a_time(self, command: RunBacklogCommand) -> int:
        previous, last, claims = "", None, ""
        while True:
            # waiting is working too: the claim is renewed on every look
            if not command.dry and not self._checkout.renew():
                self._lines.err("factory: another worker took over this checkout — the backlog run ends here.")
                return 5
            stop = self._checkout.stop_asked()
            if stop:
                self._lines.out(f"factory: {stop} exists — the backlog run stops here. Remove it to run again.")
                return 0
            # a person's requests go before the next story: a stop, what a skill works, a story to run now
            if not command.dry:
                if self._queue.take_stop():
                    return 0
                self._worker.work(())
                asked = self._take_run(())
                if asked:
                    story = asked.request["story"]
                    self._lines.out(f"══ story {story} from {asked.start}  (request {asked.request['id']})")
                    code = self._worker.run(story, asked.start)
                    self._queue.run_ended(asked.request, code)
                    if code in (0, 3) or self._skip(command, story, code):
                        last = None
                        continue
                    self._lines.err(f"factory: story {story} stopped (exit {code}) — the backlog run ends here.")
                    return code
                refreshed = self._checkout.claims()
                if refreshed and refreshed != claims:
                    self._lines.out(refreshed)
                claims = refreshed
            schedule = self._schedule.read(1, (), tuple(self._skipped))
            if not schedule.readable:
                return self._unreadable(schedule)
            if schedule.following:
                following = schedule.following[0]
                story, start = following
                if following == last:
                    self._lines.out(schedule.text)
                    self._lines.err(f"factory: {story} ran from {start} and the schedule names it there again — no "
                                    "progress, stopping.")
                    if self._skip(command, story, 1):
                        last = None
                        continue
                    return 1
                self._lines.out(f"══ story {story} from {start}")
                if command.dry:
                    self._lines.out(schedule.text)
                    self._lines.out(f"   would run: factory.sh run --story {story} --from {start}")
                    return 0
                code = self._worker.run(story, start)
                if code == 0:
                    last = following
                    continue
                if code == 3 or self._skip(command, story, code):     # 3: waits for a decision; the schedule skips it
                    last = None
                    continue
                self._lines.err(f"factory: story {story} stopped (exit {code}) — the backlog run ends here.")
                return code
            if not command.watch or not (command.stay or schedule.waits):
                self._nothing_more(schedule, command.watch)
                return self._skipped_exit()
            previous = self._waiting_note(schedule, previous, command.interval)
            last = None
            self._checkout.wait(command.interval)

    def _side_by_side(self, command: RunBacklogCommand) -> int:
        """Several stories at once, each a process of its own. A failure starts nothing more and lets the running ones
        finish; so does the stop file, a `stop` request and a signal."""
        slots = command.slots
        children: typing.Dict[str, typing.Tuple[Child, str]] = {}          # a story's process and its start
        asked: typing.Dict[str, typing.Tuple[Child, Request]] = {}         # a request's process by the request's id
        ran_for: typing.Dict[str, Request] = {}                            # a `run` request by the story it runs
        seen: typing.Set[typing.Tuple[str, str]] = set()
        failed, stopping, previous = 0, typing.cast(typing.Optional[typing.Union[int, str]], None), ""
        schedule = ScheduleRead(True, "")
        while True:
            if stopping is None:
                signal = self._checkout.signalled()
                if signal is not None:
                    stopping, failed = signal, failed or signal
                    self._lines.err("factory: stopped by a signal — no further story starts; the running ones finish.")
            if stopping is None and not self._checkout.renew():
                self._lines.err("factory: another worker took over this checkout — no further story starts.")
                stopping, failed = 5, 5
            if stopping is None:
                stop = self._checkout.stop_asked()
                if stop:
                    self._lines.out(f"factory: {stop} exists — no further story starts; the running ones finish.")
                    stopping = "stop"
            if stopping is None and self._queue.take_stop():
                stopping = "stop"
            for request_id, (child, request) in list(asked.items()):
                code = child.ended()
                if code is None:
                    continue
                del asked[request_id]
                self._queue.ended(request, code)
            for story, (child, start) in list(children.items()):
                code = child.ended()
                if code is None:
                    continue
                del children[story]
                if story in ran_for:
                    self._queue.run_ended(ran_for.pop(story), code)
                if code == 0:
                    seen.add((story, start))
                elif code != 3 and not self._skip(command, story, code):
                    self._lines.err(f"factory: story {story} stopped (exit {code}) — no further story starts; the "
                                    "running ones finish.")
                    stopping = stopping if stopping is not None else code
                    failed = failed or code
            launched = False
            if stopping is None:
                # a person's request takes the next free slot, before any story; one about a running story waits.
                # One at a time: requests work in the main checkout, and two at once would commit each other's files
                busy = set(children) | {s for _c, r in asked.values() for s in stories_of(r)}
                while len(children) + len(asked) < slots and not asked:
                    queued = self._queue.next(busy)
                    if queued is None or queued["id"] in asked:
                        break
                    asked[queued["id"]] = (self._worker.start_request(queued), queued)
                    busy |= stories_of(queued)
                    launched = True
                while len(children) + len(asked) < slots:
                    taken = self._take_run(busy)
                    if not taken:
                        break
                    story = taken.request["story"]
                    self._lines.out(f"══ story {story} from {taken.start}  (request {taken.request['id']}, "
                                    f"slots: {slots})")
                    children[story] = (self._worker.start(story, taken.start), taken.start)
                    ran_for[story] = taken.request
                    busy.add(story)
                    launched = True
                loose = sum(1 for _c, r in asked.values() if not stories_of(r))
                schedule = self._schedule.read(max(0, slots - loose), sorted(busy), tuple(self._skipped))
                if not schedule.readable:
                    stopping = failed = self._unreadable(schedule)
                for story, start in schedule.following if schedule.readable else ():
                    if len(children) + len(asked) >= slots:
                        continue
                    if (story, start) in seen:
                        self._lines.err(f"factory: {story} ran from {start} and the schedule names it there again — "
                                        "no progress, not started again.")
                        if self._skip(command, story, 1):
                            continue
                        failed = failed or 1
                        stopping = stopping if stopping is not None else 1
                        continue
                    self._lines.out(f"══ story {story} from {start}  (slots: {slots})")
                    children[story] = (self._worker.start(story, start), start)
                    launched = True
            if not children and not asked and not launched:
                if stopping is not None:
                    return failed if isinstance(stopping, int) or failed else 0
                if not command.watch or not (command.stay or schedule.waits):
                    self._nothing_more(schedule, command.watch)
                    return failed or self._skipped_exit()
                previous = self._waiting_note(schedule, previous, command.interval)
                self._checkout.wait(command.interval)
                continue
            self._checkout.pause()

    def _take_run(self, busy: typing.Iterable[str]) -> typing.Optional[RunAsked]:
        """A `run` request taken — its story starts fresh where the request named the stage."""
        asked = self._queue.take_run(busy)
        if asked is not None and asked.named:
            self._worker.fresh(asked.request["story"], asked.start)
        return asked

    def _skip(self, command: RunBacklogCommand, story: str, code: int) -> bool:
        """--keep-going: a story that stopped is set aside for the rest of this run — the schedule skips it and what
        depends on it — unless the stop concerns the whole run: the checkout taken over (5), the run's --max-stages
        (4 with the cap reached), a configuration nothing could run with (2). True when the run goes on."""
        if not command.keep_going or code in (2, 5) or (code == 4 and self._worker.capped()):
            return False
        self._skipped[story] = code
        self._lines.err(f"factory: story {story} stopped (exit {code}) — --keep-going skips it and what depends on "
                        "it; the backlog run goes on.")
        return True

    def _skipped_exit(self) -> int:
        """The run's exit once nothing more can start: 0, or the first stop's code where --keep-going skipped one."""
        if not self._skipped:
            return 0
        self._lines.err("factory: stopped in this run and skipped: "
                        + ", ".join(f"{story} (exit {code})" for story, code in self._skipped.items())
                        + " — `factory.sh status` says why.")
        return next(iter(self._skipped.values()))

    def _unreadable(self, schedule: ScheduleRead) -> int:
        self._lines.err(schedule.text)
        self._lines.err("factory: the schedule could not be read.")
        return 1

    def _nothing_more(self, schedule: ScheduleRead, watch: bool) -> None:
        self._lines.out(schedule.text)
        self._lines.out("factory: nothing more can run"
                        + (", and nothing waits on an answer that would change that" if watch else "") + ".")

    def _waiting_note(self, schedule: ScheduleRead, previous: str, interval: int) -> str:
        """Waiting is reading files, never asking an agent: an unchanged schedule is said once."""
        if schedule.text != previous:
            self._lines.out(schedule.text)
            what = "an answer" if schedule.waits else "a released story or a request"
            self._lines.out(f"factory: waiting for {what} — the schedule is read again every {interval}s; "
                            f"{self._checkout.stop_place()} ends the watch.")
        return schedule.text
