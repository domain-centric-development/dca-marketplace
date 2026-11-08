"""A request worked in its own process, wired to the project's files: the request store, its records, the checkout's
changes, the checks and use cases that settle it — and the skill the runner starts for it."""

from __future__ import annotations

import typing

from ..building_blocks import UseCaseException
from ..delivery.adapter.outgoing.files.decision_record_files import DecisionRecordFiles, RequestRecordFiles
from ..delivery.adapter.outgoing.files.journal_events import FileTransactions, JournalEventPublisher
from ..delivery.adapter.outgoing.files.handed_files import HandedFileFolder
from ..delivery.adapter.outgoing.files.request_files import PlacedRequests, RequestFiles, stamp_utc
from ..delivery.adapter.outgoing.files.scheduled_starts import ScheduledStarts
from ..delivery.adapter.outgoing.git.backlog_changes import BacklogChangeFiles
from ..delivery.adapter.outgoing.process.console_lines import ConsoleLines
from ..delivery.application.requests.check_request import CheckRequestCommand
from ..delivery.application.requests.request_queue import RequestQueue
from ..delivery.application.requests.settle_request import SettleRequestUseCase
from ..delivery.application.requests.work_request import WorkRequestUseCase
from ..delivery.application.shared.request_skill import RequestSkill
from ..delivery.application.shared.requests import Kind, Request, RequestRefused
from ..sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError
from . import delivery as wiring
from ..delivery.application.shared.request_settlement import RequestSettlement


class HeldRequests(RequestSettlement):
    """Whether a request still holds (the request check) and what the factory settles itself (the settlement) — a
    file that cannot be read on the way refuses the request, saying why."""

    def __init__(self, cwd: str, runs: str) -> None:
        self._cwd = cwd
        self._runs = runs

    def holds(self, kind: Kind, fields: typing.Mapping[str, str], words: str) -> None:
        try:
            wiring.check_request(self._cwd).execute(CheckRequestCommand(kind.name, dict(fields), words))
        except (UseCaseException, MarkdownError) as error:
            raise RequestRefused(str(error)) from error

    def settle(self, request: Request, at: str) -> typing.Optional[typing.List[str]]:
        try:
            return wiring.settlement(self._cwd, self._runs).settle(request, at)
        except (UseCaseException, MarkdownError) as error:
            raise RequestRefused(str(error)) from error


def request_queue(home: str, worker: str, placed: typing.Callable[[], typing.Any]) -> RequestQueue:
    return RequestQueue(PlacedRequests(home, placed), RequestRecordFiles(home), ScheduledStarts(home), worker,
                        ConsoleLines())


def work_request(home: str, runs: str, profile: typing.Callable[[], typing.Any],
                 lock: typing.Callable[[], typing.ContextManager[None]], skill: RequestSkill) -> WorkRequestUseCase:
    store, changes, settlement = RequestFiles(home), BacklogChangeFiles(home, runs, profile, lock), HeldRequests(home, runs)
    return WorkRequestUseCase(store, RequestRecordFiles(home), changes, skill, settlement, stamp_utc, HandedFileFolder(),
                              answers=DecisionRecordFiles(home), events=JournalEventPublisher(runs),
                              transactions=FileTransactions())


def settle_request(home: str, runs: str, profile: typing.Callable[[], typing.Any],
                   lock: typing.Callable[[], typing.ContextManager[None]]) -> SettleRequestUseCase:
    """A request the factory settles itself, written and committed at once."""
    return SettleRequestUseCase(RequestFiles(home), BacklogChangeFiles(home, runs, profile, lock), HeldRequests(home, runs),
                                stamp_utc)
