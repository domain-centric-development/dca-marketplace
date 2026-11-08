"""The requests feature's commands of the cli: a request written or settled, the queue shown."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import typing
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    shown)
from ....application.requests.list_requests import ListRequestsQuery
from ....application.requests.retry_request import RetryRequestCommand
from ....application.requests.take_back_request import TakeBackRequestCommand
from ....application.requests.write_request import WriteRequestCommand
from ....application.shared.requests import DuplicateRequest, KIND, KINDS, RequestRefused
from .....building_blocks import UseCaseException
from ..runner.run_command import settle_command
from . import root
from .common import placed


def request_command(argv: typing.Sequence[str]) -> int:
    """`factory.sh request <kind> [<target>…] [<words>…] [--story|--epic|--record|--topic|--proposal <id>]
    [--option <key>] [--from <stage>] [--by <who>] [--settle]` — `-` as the words reads them from stdin. `--settle`
    settles it at once where the factory can, writing no request (exit 3 where a skill must work it)."""
    parser = argparse.ArgumentParser(prog="factory.sh request",
                                     description="write one request the factory works before its next story")
    parser.add_argument("kind", choices=[k.name for k in KINDS])
    parser.add_argument("rest", nargs="*", help="the target the kind names, then the person's words")
    parser.add_argument("--story")
    parser.add_argument("--epic")
    parser.add_argument("--record")
    parser.add_argument("--topic")
    parser.add_argument("--proposal")
    parser.add_argument("--option", help="an answer's option key, a correction's reason code")
    parser.add_argument("--from", dest="start", help="with run: the stage the story starts at")
    parser.add_argument("--by", help="who asks (default: git user.name)")
    parser.add_argument("--file", action="append", default=[], metavar="PATH",
                        help="a file beside the words — a picture, a PDF or a text; up to five (WP-184)")
    parser.add_argument("--settle", action="store_true",
                        help="settle it now where the factory can, no request written; exit 3 where a skill must work it")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    placed()
    kind, rest = KIND[args.kind], list(args.rest)
    fields = {key: getattr(args, key) for key in ("story", "epic", "record", "topic", "proposal", "option")
              if getattr(args, key)}
    if args.start:
        fields["from"] = args.start
    for spec in kind.keys:
        names = spec.split("|")
        if any(name in fields for name in names) or not rest:
            continue
        if kind.name == "release":                  # every id given: the stories, or the one epic
            fields[names[0]] = " ".join(rest)
            rest = []
        else:
            fields[names[0]] = rest.pop(0)
    words = " ".join(rest)
    if words == "-":
        words = sys.stdin.read()
    if args.settle:
        return settle_press(kind.name, fields, words, args.by or "", args.format)
    try:
        files = []
        for given in args.file:
            with open(given, "rb") as handed:
                files.append((os.path.basename(given), handed.read()))
    except OSError as error:
        print(f"factory: request refused — {error.filename}: {error.strerror}", file=sys.stderr)
        return 2
    try:
        written = root.wiring.write_request(os.getcwd()).execute(
            WriteRequestCommand(kind.name, fields, words, args.by or "", tuple(files)))
        request_id, path = written.id, written.path
    except DuplicateRequest as same:
        print(f"factory: {same}")
        return 0
    except (UseCaseException, GateError) as error:
        print(f"factory: request refused — {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(dict(id=request_id, path=shown(path))))
    else:
        print(f"factory: request {request_id} written ({shown(path)}) — the factory works it before its next story")
    return 0


def settle_press(kind_name: str, fields: typing.Mapping[str, typing.Any], words: str, by: str, fmt: str) -> int:
    """`request … --settle`: settled now, or exit 3 — the caller then runs the action's skill, as before."""
    try:
        # the runner's own lines go to stderr where the caller reads one JSON object from stdout
        with contextlib.redirect_stdout(sys.stderr) if fmt == "json" else contextlib.nullcontext():
            code, request_id, commit = settle_command(os.getcwd(), kind_name, fields, words, by)
    except DuplicateRequest as same:
        print(json.dumps(dict(id=same.existing, settled=False, queued=True)) if fmt == "json" else f"factory: {same}")
        return 0
    except (UseCaseException, GateError) as error:
        print(f"factory: request refused — {error}", file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps(dict(id=request_id, settled=code == 0, commit=commit)))
    elif code == 0:
        print(f"factory: {kind_name} settled by the factory, no tool" + (f" — committed {commit}" if commit else ""))
    elif code == 3:
        print(f"factory: {kind_name} needs its skill — nothing written")
    return code


def requests_command(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory.sh requests", description="the requests and their state")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--drop", metavar="ID", help="take a request back (not while it runs)")
    parser.add_argument("--retry", metavar="ID", help="queue a failed request again")
    args = parser.parse_args(argv)
    placed()
    try:
        if args.drop:
            root.wiring.take_back_request(os.getcwd()).execute(TakeBackRequestCommand(args.drop))
            print(f"factory: request {args.drop} dropped")
            return 0
        if args.retry:
            root.wiring.retry_request(os.getcwd()).execute(RetryRequestCommand(args.retry))
            print(f"factory: request {args.retry} queued again")
            return 0
    except (RequestRefused, OSError) as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    return requests_view(os.getcwd(), args.format)


def requests_view(cwd: str, fmt: str = "text") -> int:
    """`factory.sh requests`: every request with its state, oldest first."""
    model = root.wiring.list_requests(cwd).execute(ListRequestsQuery())
    if fmt == "json":
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0
    rows = model["requests"]
    if not rows:
        print(f"requests: none — `factory.sh request <kind> …` writes one ({model['store']})")
        return 0
    for row in rows:
        extra = row["error"] or (f"asks: {row['record']}" if row["record"] else "") or \
            (f"{row['worker']} since {row['started']}" if row["state"] == "running" else "")
        print(f"{row['id']}  {row['state']:<8} {row['kind']:<9} {row['target']}  ({row['by']})"
              + (f" — {extra}" if extra else ""))
    print("requests: " + ", ".join(f"{n} {s}" for s, n in model["counts"].items() if n))
    return 0
