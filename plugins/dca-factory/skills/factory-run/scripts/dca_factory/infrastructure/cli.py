"""The cli's command line across the contexts: the rulebook's `--rules`, the spec's `--spec`, everything else
delivery's. Each command line and the composition root it builds its use cases from are imported for the command
that is given, and only then: the runner calls the cli many times per story, and a call loads what it asks for."""

from __future__ import annotations

import typing

from .workflow import load_workflow

# the stages and the rules, from their repositories — once per process
load_workflow()


def wire() -> None:
    """Every command line wired at once — for a caller in this process that uses several (the suite's unit cases);
    `main` wires only the one a command needs."""
    from ..delivery.adapter.incoming.cli import root as cli_root
    from ..delivery.adapter.incoming.runner import run_command
    from ..delivery.adapter.incoming.web import service as web_service
    from ..rulebook.adapter.incoming.cli import rules_command
    from ..spec.adapter.incoming.cli import spec_command
    from ..delivery.adapter.incoming.cli import question_command
    from . import delivery, questions, rulebook, runner, spec
    question_command.wire(questions)
    cli_root.wire(delivery)
    run_command.wire(runner)
    rules_command.wire(rulebook)
    spec_command.wire(spec)
    web_service.wire(delivery)


def main(argv: typing.Sequence[str]) -> int:
    if list(argv[:1]) == ["--sh"]:                # `factory.sh`, handed over at once: its own command line and root
        from . import shell
        return shell.main(argv[1:])
    if "--rules" in argv:
        from ..rulebook.adapter.incoming.cli import rules_command
        from . import rulebook
        rules_command.wire(rulebook)
        return rules_command.main(argv)
    if "--spec" in argv:
        from ..spec.adapter.incoming.cli import spec_command
        from . import spec
        spec_command.wire(spec)
        return spec_command.main(argv)
    from ..delivery.adapter.incoming.cli import question_command
    asked = question_command.parse(argv)
    if asked is not None:                     # the runner's questions: the stage table, a place, a profile value
        from . import questions
        question_command.wire(questions)
        return question_command.main(asked)
    from ..delivery.adapter.incoming.cli import cli_command
    from ..delivery.adapter.incoming.cli import root as cli_root
    from ..delivery.adapter.incoming.runner import run_command
    from ..delivery.adapter.incoming.web import service as web_service
    from . import delivery, runner
    cli_root.wire(delivery)
    run_command.wire(runner)
    web_service.wire(delivery)
    return cli_command.main(argv)
