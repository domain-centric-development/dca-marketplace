"""The cli's command line across the contexts: the rulebook's `--rules`, everything else delivery's."""

from __future__ import annotations

import typing

from ..delivery.adapter.incoming.cli import cli_command
from ..rulebook.adapter.incoming.cli import rules_command
from .workflow import load_workflow

# the stages and the rules, from their repositories — once per process
load_workflow()


def main(argv: typing.Sequence[str]) -> int:
    if "--rules" in argv:
        return rules_command.main(argv)
    return cli_command.main(argv)
