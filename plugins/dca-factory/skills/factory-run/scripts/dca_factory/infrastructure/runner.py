"""The runner wired: the run of `factory.sh run`, of a request's own process and of a settled press — the main
checkout it stands in, the places its profile sets, the worker whose claim it runs under."""

from __future__ import annotations

import argparse
import os
import typing

from ..delivery.application.requests.check_request import CheckRequestCommand
from ..delivery.application.requests.work_request import RequestWorked
from ..delivery.application.shared.requests import KIND, Request
from ..runner import Run
from ..sharedkernel.adapter.outgoing.profile.profile_files import (
    place,
    read_profile,
    resolve_profile,
    set_places,
)
from . import delivery


def placed(cwd: str) -> None:
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))


def run_for(options: argparse.Namespace) -> Run:
    """The run in the checkout it is started in — or, as a story's child, under its parent's worker."""
    cwd = os.getcwd()
    home = os.environ.get("FACTORY_HOME") or os.path.realpath(cwd)
    placed(cwd)
    worker = os.environ.get("FACTORY_RUNNER_WORKER") if options.child else None
    return Run(options, home, place("runs"), worker=worker)  # type: ignore[no-untyped-call]


def request_run_for(options: argparse.Namespace, worker: typing.Optional[str]) -> Run:
    """The run a request's own process works under: the runner's claim (`worker`), else one of its own."""
    cwd = os.getcwd()
    placed(cwd)
    return Run(options, os.path.realpath(cwd), place("runs"), worker=worker)  # type: ignore[no-untyped-call]


def settle(cwd: str, kind_name: str, fields: typing.Mapping[str, str], words: str, by: str,
           options: argparse.Namespace) -> typing.Tuple[Request, typing.Optional[RequestWorked]]:
    """A press settled at once where the factory can: the request as it would be written, and what settling it said
    — None where a skill must work it. The settle and its commit hold the checkout's commit lock, as the factory's
    own requests do, whether a factory is up or not."""
    placed(cwd)
    checked = delivery.check_request(cwd).execute(CheckRequestCommand(kind_name, dict(fields), words,
                                                                      against_waiting=True))
    worker = os.environ.get("FACTORY_RUNNER_WORKER")
    run = Run(options, os.path.realpath(cwd), place("runs"), worker=worker)  # type: ignore[no-untyped-call]
    request = run.press(kind_name, checked.fields, checked.words, by)  # type: ignore[no-untyped-call]
    return request, run.request_use_case().settle(request, KIND[kind_name])  # type: ignore[no-untyped-call]
