"""The runner's questions to the cli — the stage table as bash lines, a place, one of the profile's values — answered
without the rest of the cli's command line. A script asks for the stage table in one call and a process asks the
profile many times per story; the whole command line imports every view and use case first, a process start's worth
of time for one line of answer. Only exactly these argument shapes are taken here (`parse`); anything else, a
mistake among it, goes to the cli's whole command line, which answers it or says what is wrong."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
import typing

from ....application.delivery.show_stage_table import ShowStageTableInputPort, ShowStageTableQuery
from ....application.profile.ask_profile import AskProfileInputPort, AskProfileQuery, Question
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, place, read_profile, resolve_profile, set_places)

Model = typing.Dict[str, typing.Any]

SHELL_WORD = re.compile(r"[a-z][a-z0-9_-]*")
FILE_WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*")


class QuestionRoot(typing.Protocol):
    """What the questions take from the composition root."""

    def show_stage_table(self) -> ShowStageTableInputPort: ...

    def ask_profile(self, path: typing.Optional[str]) -> AskProfileInputPort: ...


wiring: QuestionRoot


def wire(root: QuestionRoot) -> None:
    global wiring
    wiring = root


class _Strict(argparse.ArgumentParser):
    def error(self, message: str) -> typing.NoReturn:
        raise ValueError(message)


def parse(argv: typing.Sequence[str]) -> typing.Optional[argparse.Namespace]:
    """<argv> as one of the runner's questions, or None for the cli's whole command line."""
    parser = _Strict(add_help=False, allow_abbrev=False)
    parser.add_argument("--stages", action="store_true")
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--place")
    parser.add_argument("--get")
    parser.add_argument("--command-heads", action="store_true")
    parser.add_argument("--carriers", action="store_true")
    parser.add_argument("--carrier-lines", action="store_true")
    parser.add_argument("--model", nargs=2)
    for flag in ("--root", "--profile", "--epics", "--runs"):
        parser.add_argument(flag)
    try:
        args, rest = parser.parse_known_args(list(argv))
    except ValueError:
        return None
    if rest or args.stages != args.shell or (args.place is not None and args.place not in DEFAULTS):
        return None
    asked = [args.stages, args.get is not None, args.command_heads, args.carriers, args.carrier_lines,
             args.model is not None]
    if sum(asked) > 1 or (sum(asked) == 1 and args.place is not None and not args.stages) \
            or (sum(asked) == 0 and args.place is None):
        return None
    return args


def main(args: argparse.Namespace) -> int:
    """One question answered, the places set as the whole command line sets them."""
    cwd = os.path.abspath(args.root or ".")
    os.chdir(cwd)
    profile_path = resolve_profile(args.profile or os.environ.get("FACTORY_PROFILE") or None, cwd)
    set_places(read_profile(profile_path), epics=args.epics, runs=args.runs)
    if args.stages:
        return stages_shell(wiring.show_stage_table().execute(
            ShowStageTableQuery((args.place,) if args.place else (), with_tools=True)))
    if args.get is not None:
        return answer(profile_path, Question.VALUE, key=args.get)
    if args.command_heads:
        return answer(profile_path, Question.COMMAND_HEADS)
    if args.carriers:
        return answer(profile_path, Question.CARRIERS)
    if args.carrier_lines:
        return answer(profile_path, Question.CARRIER_LINES)
    if args.model is not None:
        return answer(profile_path, Question.MODEL, tool=args.model[0], stage=args.model[1])
    print(place(args.place))
    return 0


def answer(profile_path: typing.Optional[str], question: Question, **fields: str) -> int:
    """The profile's answer to one question, a line per item (`AskProfileUseCase`)."""
    print("\n".join(wiring.ask_profile(profile_path).execute(AskProfileQuery(question, **fields))))
    return 0


def stages_shell(table: Model) -> int:
    """The stage table (`ShowStageTableUseCase`) as a shell script reads it in one call, one bash assignment per
    line, then the tool table and the places asked for, quoted. Every name is checked to be a plain word."""
    names = [row["name"] for row in table["rows"]] + list(table["windows"]) + sorted({k for k, _s in table["kinds"]})
    bad = [name for name in names if not SHELL_WORD.fullmatch(name)]
    bad += [file for file in table["files"].values() if not FILE_WORD.fullmatch(file)]
    if bad:
        print(f"factory-cli: the stage table holds a name the runner cannot take as a word: {', '.join(bad)}",
              file=sys.stderr)
        return 2
    if table["tools"] is None:
        return 2
    array = lambda name, values: f"{name}=({' '.join(values)})"
    lines = [array("STAGES", table["order"]), array("STEPS", table["steps"])]
    lines += [array(f"{window.upper().replace('-', '_')}_STAGES", stages) for window, stages in table["windows"].items()]
    lines += [array("PRE_GATED", table["pre_gated"]), array("POST_GATED", table["post_gated"]),
              array("RED_STAGES", table["red"]), array("GUARDED_STAGES", table["guarded"])]
    lines.append("KIND_STAGES=' " + " ".join(f"{kind}:{stage}" for kind, stage in table["kinds"]) + " '")
    lines.append("STAGE_FILES=' " + " ".join(f"{name}:{file}" for name, file in table["files"].items()) + " '")
    lines += table["tools"] + [f"PLACE_{key.upper()}={shlex.quote(value)}" for key, value in table["places"].items()]
    print("\n".join(lines))
    return 0
