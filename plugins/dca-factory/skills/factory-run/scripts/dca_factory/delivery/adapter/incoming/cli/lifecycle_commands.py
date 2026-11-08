"""The lifecycle feature's commands of the cli: the factory up and down, the page served."""

from __future__ import annotations

import argparse
import os
import sys
import typing
from ....application.lifecycle.start_factory import StartFactoryCommand
from ....application.lifecycle.stop_factory import StopFactoryCommand
from ....application.lifecycle.end_page import EndPageCommand
from ....application.lifecycle.start_page import StartPageCommand
from ....application.lifecycle.show_running_page import ShowRunningPageQuery
from ..web import service as web
from . import root
from .common import placed


def up_command(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory.sh up", description="start the factory in the background")
    parser.add_argument("--serve", action="store_true", help="the page too")
    parser.add_argument("--port", type=int)
    parser.add_argument("--by")
    parser.add_argument("--requests", action="store_true",
                        help="the worker for a person's requests alone — the backlog stays as it is (the page starts it)")
    args, run_args = parser.parse_known_args(argv)
    allowed = {"--tool", "--parallel", "--interval", "--max-stages", "--story-budget", "--keep-going",
               "--separate-stages", "--shared-builder", "--shared-verifier"}
    stray = [a for a in run_args if a.startswith("-") and a not in allowed]
    if stray:
        print(f"factory: up takes no {' '.join(stray)} — the runner's flags it passes on: {' '.join(sorted(allowed))}",
              file=sys.stderr)
        return 2
    placed()
    return root.wiring.start_factory().execute(StartFactoryCommand(tuple(run_args), args.serve, args.port, args.by or "",
                                                              backlog=not args.requests))


def down_command(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory.sh down", description="end the factory after its running stage")
    parser.add_argument("--now", action="store_true", help="interrupt the running stage too")
    parser.add_argument("--no-wait", action="store_true", help="say stop and return at once")
    parser.add_argument("--by")
    args = parser.parse_args(argv)
    placed()
    return root.wiring.stop_factory().execute(StopFactoryCommand(args.now, not args.no_wait, args.by or ""))


def serve_command(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory.sh serve", description="the factory's page, on this machine alone")
    parser.add_argument("--port", type=int)
    parser.add_argument("--open", action="store_true", help="open it in the browser")
    parser.add_argument("--background", action="store_true", help="start it detached and return")
    parser.add_argument("--stop", action="store_true",
                        help="end the page that runs here; its requests' worker ends too unless the backlog is on")
    parser.add_argument("--by-up", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fixture", metavar="NAME",
                        help="the page against canned views that hold every state — all-states or empty; writes nothing")
    args = parser.parse_args(argv)
    placed()
    if args.fixture:
        return web.serve_here(os.getcwd(), args.port, args.open, fixture=args.fixture)
    if args.stop:
        return root.wiring.end_page().execute(EndPageCommand())
    if args.by_up:
        return web.serve_here(os.getcwd(), args.port, by_up=True)
    if args.background:
        started = root.wiring.start_page().execute(StartPageCommand(args.port))
        if started.running:
            print(f"factory: the page runs already — {started.running['url']}")
        return started.exit
    served = root.wiring.show_running_page().execute(ShowRunningPageQuery())
    if served:
        print(f"factory: the page runs already — {served['url']}")
        return 0
    return web.serve_here(os.getcwd(), args.port, args.open)
