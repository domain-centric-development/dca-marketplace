"""The runner wired: the run of `factory.sh run`, of a request's own process and of a settled press — the main
checkout it stands in, the places its profile sets, the worker whose claim it runs under."""

from __future__ import annotations

import argparse
import os
import typing

from ..delivery.application.requests.check_request import CheckRequestCommand
from ..delivery.application.requests.work_request import RequestWorked
from ..delivery.application.shared.requests import KIND, Request
from ..delivery.adapter.incoming.runner.usage import book_request_usage
from ..delivery.adapter.outgoing.process.console_lines import ConsoleLines
from ..delivery.application.backlog.run_backlog import RunBacklogCommand, RunBacklogUseCase
from ..delivery.application.delivery.integrate_story import IntegrateStoryCommand, IntegrateStoryUseCase
from ..delivery.application.delivery.run_story import RunStoryCommand, RunStoryUseCase
from ..delivery.application.requests.request_queue import RequestQueue
from ..delivery.application.requests.work_request import WorkRequestCommand, WorkRequestUseCase
from ..delivery.domain.model.stage import Window
from ..delivery.adapter.outgoing.process.runner_ports import (
    RunnerBacklog, RunnerIntegration, RunnerRequestSkill, RunnerStages)
from ..delivery.adapter.outgoing.process.runner_process import Run
from ..sharedkernel.adapter.outgoing.profile.profile_files import (
    place,
    read_profile,
    resolve_profile,
    set_places,
)
from . import delivery
from . import requests


class RunnerCases:
    """The use cases a step of a run starts, tied to the run's adapters here — the run calls them, never builds them
    (`RunCases`)."""

    def run_story(self, run: Run, tool: str, story: str, start: typing.Optional[str], dry: bool, gate_first: bool,
                  shared: typing.FrozenSet[Window]) -> int:
        return RunStoryUseCase(RunnerStages(run, tool), ConsoleLines()).execute(
            RunStoryCommand(story, start, dry, gate_first, shared))

    def integrate(self, run: Run, tool: str, story: str, dry: bool) -> typing.Optional[int]:
        return self._integration(run, tool).execute(IntegrateStoryCommand(story, dry))

    def resolve(self, run: Run, tool: str, story: str, out: str) -> typing.Optional[int]:
        return self._integration(run, tool).resolve(story, out)

    def run_backlog(self, run: Run, tool: str, slots: int, watch: bool, interval: int, dry: bool) -> int:
        backlog = RunnerBacklog(run, tool)
        return RunBacklogUseCase(backlog, backlog, backlog, self.queue(run), ConsoleLines()).execute(
            RunBacklogCommand(slots, watch, interval, dry, run.keep_going, run.stay))

    def queue(self, run: Run) -> RequestQueue:
        return requests.request_queue(run.home, run.worker, run.profile)

    def work_request(self, run: Run, request_id: str, tool: str) -> RequestWorked:
        return self._work_request(run).execute(WorkRequestCommand(request_id, tool, run.worker))

    def book_request_cost(self, run: Run, request_id: str, tool: str, measured: str) -> None:
        book_request_usage(delivery.book_request_cost(run.home, place("runs")), request_id, tool, measured)

    @staticmethod
    def _integration(run: Run, tool: str) -> IntegrateStoryUseCase:
        return IntegrateStoryUseCase(RunnerIntegration(run, tool), ConsoleLines())

    @staticmethod
    def _work_request(run: Run) -> WorkRequestUseCase:
        return requests.work_request(run.home, run.runs_rel, run.profile, run.locked,
                                     RunnerRequestSkill(run))


def placed(cwd: str) -> None:
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))


def run_for(options: argparse.Namespace) -> Run:
    """The run in the checkout it is started in — or, as a story's child, under its parent's worker."""
    cwd = os.getcwd()
    home = os.environ.get("FACTORY_HOME") or os.path.realpath(cwd)
    placed(cwd)
    worker = os.environ.get("FACTORY_RUNNER_WORKER") if options.child else None
    return Run(options, home, place("runs"), worker=worker, cases=RunnerCases())


def request_run_for(options: argparse.Namespace, worker: typing.Optional[str]) -> Run:
    """The run a request's own process works under: the runner's claim (`worker`), else one of its own."""
    cwd = os.getcwd()
    placed(cwd)
    return Run(options, os.path.realpath(cwd), place("runs"), worker=worker,
               cases=RunnerCases())


def settle(cwd: str, kind_name: str, fields: typing.Mapping[str, str], words: str, by: str,
           options: argparse.Namespace) -> typing.Tuple[Request, typing.Optional[RequestWorked]]:
    """A press settled at once where the factory can: the request as it would be written, and what settling it said
    — None where a skill must work it. The settle and its commit hold the checkout's commit lock, as the factory's
    own requests do, whether a factory is up or not."""
    placed(cwd)
    checked = delivery.check_request(cwd).execute(CheckRequestCommand(kind_name, dict(fields), words,
                                                                      against_waiting=True))
    worker = os.environ.get("FACTORY_RUNNER_WORKER")
    run = Run(options, os.path.realpath(cwd), place("runs"), worker=worker,
              cases=RunnerCases())
    request = run.press(kind_name, checked.fields, checked.words, by)
    return request, RunnerCases._work_request(run).settle(request, KIND[kind_name])
