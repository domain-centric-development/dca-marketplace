"""`factory-cli.py --rules [--stage <s>] [--kind <k>] [--format md|json] [--check]` — the rulebook, generated from
where the rules are written; `--check` exits 1 when the rulebook itself does not hold (an id used twice, a cited id
no rule has, a stage no row has)."""

from __future__ import annotations

import argparse
import os
import sys
import typing

from .....infrastructure import rulebook as wiring
from ....application.show_rulebook import ShowRulebookQuery
from .rules_view import render


def main(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory-cli.py --rules", description="the factory's rules")
    parser.add_argument("--rules", action="store_true", required=True)
    parser.add_argument("--stage", help="only the rules that hold at this stage")
    parser.add_argument("--kind", help="only the rules that hold for this story kind")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--check", action="store_true",
                        help="print what does not hold in the rulebook itself, exit 1 when anything does")
    args = parser.parse_args(list(argv))
    view = wiring.show_rulebook(os.getcwd()).execute(ShowRulebookQuery(args.stage, args.kind))
    if args.check:
        for problem in view["problems"]:
            print(f"rules: {problem}", file=sys.stderr)
        if not view["skills"]:
            print("rules: no skills folder found — the instructed rules were not read", file=sys.stderr)
        print(f"rules: {len(view['rules'])} rule(s), {len(view['problems'])} problem(s)")
        return 1 if view["problems"] or not view["skills"] else 0
    sys.stdout.write(render(view, args.format))
    return 0
