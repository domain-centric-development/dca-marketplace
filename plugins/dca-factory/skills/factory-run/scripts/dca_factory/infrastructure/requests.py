"""A request worked in its own process, wired to the project's files: the request store, its records, the checkout's
changes, the checks and use cases that settle it — and the skill the runner starts for it."""

from __future__ import annotations

import datetime
import typing

from ..building_blocks import UseCaseException
from ..delivery.adapter.outgoing.files.backlog_files import BacklogFiles
from ..delivery.adapter.outgoing.files.decision_record_files import RequestRecordFiles
from ..delivery.adapter.outgoing.files.request_files import RequestFiles, stamp_utc
from ..delivery.adapter.outgoing.git.backlog_changes import BacklogChangeFiles
from ..delivery.adapter.outgoing.process.console_lines import ConsoleLines
from ..delivery.application.requests.check_request import CheckRequestCommand
from ..delivery.application.requests.request_queue import RequestQueue
from ..delivery.application.requests.work_request import WorkRequestUseCase
from ..delivery.application.schedule.schedule_backlog import schedule_backlog
from ..delivery.application.schedule.start_story import start_story
from ..delivery.application.shared.request_skill import RequestSkill
from ..delivery.application.shared.requests import Kind, Request, RequestRefused
from ..delivery.application.shared.story_starts import Start
from ..sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError
from ..sharedkernel.adapter.outgoing.profile.profile_files import place
from . import delivery as wiring


class HeldRequests:
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


class ScheduledStarts:
    """Where a story begins, as the schedule of the checkout reads it now."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def start(self, story: str) -> typing.Optional[Start]:
        schedule = schedule_backlog(BacklogFiles(self._cwd, place("epics"), place("runs")),
                                    datetime.datetime.now(datetime.timezone.utc), 1)
        return start_story(schedule, story, 1)


class PlacedRequests(RequestFiles):
    """The request store where the profile puts it now: the places are set again before every look — a person may
    edit the profile while a run waits, and the runner moves between the checkout and a worktree."""

    def __init__(self, cwd: str, placed: typing.Callable[[], typing.Any]) -> None:
        super().__init__(cwd)
        self._placed = placed

    def all(self) -> typing.List[Request]:
        self._placed()
        return super().all()

    def find(self, request_id: str) -> Request:
        self._placed()
        return super().find(request_id)


def request_queue(home: str, worker: str, placed: typing.Callable[[], typing.Any]) -> RequestQueue:
    return RequestQueue(PlacedRequests(home, placed), RequestRecordFiles(home), ScheduledStarts(home), worker,
                        ConsoleLines())


def work_request(home: str, runs: str, profile: typing.Callable[[], typing.Any],
                 lock: typing.Callable[[], typing.ContextManager[None]], skill: RequestSkill) -> WorkRequestUseCase:
    return WorkRequestUseCase(RequestFiles(home), RequestRecordFiles(home), BacklogChangeFiles(home, runs, profile, lock),
                              skill, HeldRequests(home, runs), stamp_utc)
