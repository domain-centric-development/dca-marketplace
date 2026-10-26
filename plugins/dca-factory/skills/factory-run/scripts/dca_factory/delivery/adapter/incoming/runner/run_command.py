"""`factory.sh run`, a request's own process and a settled press: the runner's entry points — the arguments, the
signals, the exit codes —, the run itself built by the composition root (`infrastructure/runner.py`).

Exit codes: 0 the story ran through, 1 a failure, 2 a usage error, 3 it stopped for a decision, 4 at --max-stages or
--story-budget, 5 another worker holds the checkout, 7 the pipeline or a person's file changed under it, 124 a stage
ran past its time limit is reported as a failure (1), 129/130/143 a hang-up, an interrupt, a TERM.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import sys
import typing

from .....infrastructure import runner as wiring
from ....application.shared.run_stop import SIGNAL_EXITS, Stopped
from ....domain.model.stage import PIPELINE, Trait


def err(text: str) -> None:
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def line_buffered() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(line_buffering=True)  # type: ignore[union-attr]


def run_options(argv: typing.Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="factory.sh run", description="the runner, started by `factory.sh run`")
    parser.add_argument("--story")
    parser.add_argument("--tool", default="")
    parser.add_argument("--from", dest="start", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--stay", action="store_true",
                        help="with --watch: keep waiting when nothing waits on an answer — for a person's requests")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--max-stages", type=int, default=0)
    parser.add_argument("--story-budget", type=int, default=0)
    parser.add_argument("--builder", choices=("shared", "separate"), default="shared")
    parser.add_argument("--verifier", choices=("shared", "separate"), default="shared")
    parser.add_argument("--parallel", default="")
    parser.add_argument("--child", action="store_true", help="one story of a parallel run, under its parent's claim")
    parser.add_argument("--keep-going", action="store_true",
                        help="a stopped story is skipped with what depends on it; the backlog run ends when nothing "
                             "can start")
    return parser.parse_args(argv)


def run_main(argv: typing.Sequence[str]) -> int:
    """`factory.sh run` once its checks passed: the claim, the pipeline's hash, the story or the backlog, and the
    claim and the lock given back however the run ends."""
    line_buffered()
    options = run_options(argv)
    run = wiring.run_for(options)

    def stop(signum: int, _frame: typing.Any) -> None:
        name = signal.Signals(signum).name
        err("factory: stopped by a hang-up — after the running stage, nothing more starts" if name == "SIGHUP" else
            "factory: stopped by a signal — after the running stage, nothing more starts")
        run.pending = SIGNAL_EXITS[name]
        if run.sleeping:
            run.pending = None
            raise Stopped(SIGNAL_EXITS[name])
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    try:
        code = run_start(run, options)
        run.checkpoint()
        return code
    except Stopped as stopped:
        return stopped.code
    except KeyboardInterrupt:
        err("factory: interrupted — the claim and the lock are given back; the stage's files stay as they are.")
        return SIGNAL_EXITS["SIGINT"]
    finally:
        run.drop_lock()
        if not options.child:
            run.release()


def run_start(run: typing.Any, options: argparse.Namespace) -> int:
    """A story — from the stage named, else from where its files say — or the backlog."""
    tool = options.tool or "stand-in"
    if not options.dry_run and not options.child:
        code = run.tools_ready(tool)
        if code:
            return int(code)
    if options.child:
        run.gate_first = False
        return int(run.run_story(options.story, tool, options.start, False))
    if options.story:
        story, start = options.story, options.start
        if not start:
            # No stage named: the story starts where its files say, as the backlog run would start it.
            code, answer = run.cli("--story", story, "--start", "--slots", "1", quiet=False)
            if code != 0:
                return int(code)
            state, start, detail = field_of(answer, "state"), field_of(answer, "start"), field_of(answer, "detail")
            if start in ("none", ""):
                if state == "delivered":
                    print(f"factory: story {story} is delivered" + (f" ({detail})" if detail else "")
                          + " — nothing runs.")
                    return 0
                if state == "waiting":
                    err(f"factory: story {story} waits for {detail} — answer it with /factory-decisions.")
                    return 3
                if state == "running":
                    err(f"factory: story {story} is running ({detail}) — one run at a time.")
                    return 5
                err(f"factory: story {story} is {state}" + (f" — {detail}" if detail else "") + ".")
                err(f"factory:   nothing runs; name the stage to run it anyway: factory.sh run --story {story} "
                    "--from <stage>")
                return 1
            print(f"factory: story {story} starts at {start}" + (f" — {detail}" if detail else ""))
        else:
            names = [s.name.value for s in PIPELINE if Trait.IN_ORDER in s.traits] \
                + [s.name.value for s in PIPELINE if Trait.IN_ORDER not in s.traits]
            if start not in names:
                err(f"factory: --from {start} names no stage ({' '.join(names)}) — nothing ran, the rounds are as "
                    "they were")
                return 2
            if not options.dry_run:
                run.reset_rounds(story, start)
        run.gate_first = True
        if not options.dry_run:
            code = run.take_checkout() or run.guard_pipeline_start()
            if code:
                return int(code)
            if options.start:
                run.gates.fresh_window(story)
        return int(run.run_story(story, tool, start, options.dry_run))
    if not options.dry_run:
        code = run.take_checkout() or run.guard_pipeline_start()
        if code:
            return int(code)
    return int(run.run_backlog(tool, options.watch, max(1, min(3600, options.interval)), options.dry_run))


def request_main(argv: typing.Sequence[str]) -> int:
    """`factory-cli.py --work-request <id> [--tool <tool>]`: one request worked, as the runner starts it — under the
    runner's claim (FACTORY_RUNNER_WORKER), or, started alone, under a claim of its own."""
    line_buffered()
    parser = argparse.ArgumentParser(prog="factory-cli.py --work-request")
    parser.add_argument("request")
    parser.add_argument("--tool", default="")
    given = parser.parse_args(argv)
    worker = os.environ.get("FACTORY_RUNNER_WORKER")
    run = wiring.request_run_for(run_options(["--tool", given.tool]), worker)
    tool = given.tool or run.default_tool()
    if not worker:
        code = run.tools_ready(tool) or run.take_checkout()
        if code:
            return int(code)
    try:
        return said(run.work_request(given.request, tool))
    except Stopped as stopped:
        return stopped.code
    except KeyboardInterrupt:
        return SIGNAL_EXITS["SIGINT"]
    finally:
        if not worker:
            run.release()


def said(worked: typing.Any) -> int:
    """What a request's use case said on its way, printed where the person reads it; its exit code."""
    for stream, line in worked.said:
        (err if stream == "err" else print)(line)
    return int(worked.code)


def settle_command(cwd: str, kind_name: str, fields: typing.Mapping[str, str], words: str,
                   by: str) -> typing.Tuple[int, str, str]:
    """`factory.sh request <kind> … --settle`: the request settled at once where the factory can, no file written and
    no tool started — a press in a session's view takes the same shortcut a page's request takes. Exit 0 settled (and
    committed), 3 where a skill must work it (nothing written), 2 refused, 1 failed."""
    request, settled = wiring.settle(cwd, kind_name, fields, words, by, run_options([]))
    if settled is None:
        return 3, request["id"], ""
    return said(settled), request["id"], settled.commit


def field_of(text: str, key: str) -> str:
    return next((line[len(key) + 2:] for line in text.split("\n") if line.startswith(f"{key}: ")), "")
