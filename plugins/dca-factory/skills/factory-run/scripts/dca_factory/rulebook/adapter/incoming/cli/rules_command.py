"""`factory-cli.py --rules [--stage <s>] [--kind <k>] [--story <id>] [--format md|json|svg|mermaid] [--check]` — the rulebook, generated from
where the rules are written; `--check` exits 1 when the rulebook itself does not hold (an id used twice, a cited id
no rule has, a stage no row has)."""

from __future__ import annotations

from ....domain.model.rule import KindName

import argparse
import os
import sys
import typing

from ....application.show_rulebook import ShowRulebookQuery, ShowRulebookInputPort


class RulesRoot(typing.Protocol):
    """What this command line takes from the composition root — given at start (`wire`), never imported."""

    def show_rulebook(self, cwd: str) -> ShowRulebookInputPort: ...


#: the composition root, given by `wire` before the command line runs
wiring: RulesRoot


def wire(root: RulesRoot) -> None:
    """The composition root this command line builds its use cases from."""
    global wiring
    wiring = root
from .rules_view import render


def main(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory-cli.py --rules", description="the factory's rules")
    parser.add_argument("--rules", action="store_true", required=True)
    parser.add_argument("--stage", help="only the rules that hold at this stage")
    parser.add_argument("--kind", choices=[kind.value for kind in KindName],
                        help="only the rules that hold for this story kind")
    parser.add_argument("--story", help="mark the rules that fired in the story's last gate runs")
    parser.add_argument("--format", choices=("md", "json", "svg", "mermaid"), default="md",
                        help="svg, mermaid: the flow of --kind (story when none) as a drawing")
    parser.add_argument("--check", action="store_true",
                        help="print what does not hold in the rulebook itself, exit 1 when anything does")
    args = parser.parse_args(list(argv))
    view = wiring.show_rulebook(os.getcwd()).execute(ShowRulebookQuery(args.stage, args.kind, args.story))
    if args.check:
        for problem in view["problems"]:
            print(f"rules: {problem}", file=sys.stderr)
        if not view["skills"]:
            print("rules: no skills folder found — the instructed rules were not read", file=sys.stderr)
        if view.get("unexplained"):
            print(f"rules: information — {len(view['unexplained'])} told rule(s) say `why: unknown`, a bet nobody can "
                  f"name the failure of: {', '.join(view['unexplained'])}")
        print(f"rules: {len(view['rules'])} rule(s), {len(view['problems'])} problem(s)")
        return 1 if view["problems"] or not view["skills"] else 0
    sys.stdout.write(render(view, args.format))
    return 0
