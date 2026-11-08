"""The cli's command line across the contexts: the rulebook's `--rules`, the spec's `--spec`, everything else
delivery's."""

from __future__ import annotations

import typing

from ..delivery.adapter.incoming.cli import cli_command
from ..delivery.adapter.incoming.runner import run_command
from ..delivery.adapter.incoming.web import service as web_service
from ..rulebook.adapter.incoming.cli import rules_command
from ..spec.adapter.incoming.cli import spec_command
from .workflow import load_workflow

from . import delivery, rulebook, runner, spec


def wire() -> None:
    """Every command line of the cli given the composition root it builds its use cases from."""
    cli_command.wire(delivery)
    run_command.wire(runner)
    rules_command.wire(rulebook)
    spec_command.wire(spec)
    web_service.wire(delivery)


# the stages and the rules, from their repositories, and the command lines wired — once per process
load_workflow()
wire()


def main(argv: typing.Sequence[str]) -> int:
    if "--rules" in argv:
        return rules_command.main(argv)
    if "--spec" in argv:
        return spec_command.main(argv)
    return cli_command.main(argv)
