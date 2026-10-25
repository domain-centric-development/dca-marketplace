"""The factory's pipeline as one package — `story-gate.py` and `factory-cli.py` beside it are its entry points.

Built the way it teaches (WP-152; the map and the glossaries in the plugin's `docs/`):

    building_blocks   the markers of DCA's tactical patterns and ports, outside every context
    delivery/         the bounded context delivery: backlog, decisions, delivery, description, cost — in layers
    spec/             the bounded context spec: what holds, merged from a story's delta; `spec/api` its open host
    sharedkernel/     what the contexts read alike: a project's markdown
    web/              the host across the contexts: the page and its server
    infrastructure/   the composition root: each use case with its adapters

and the modules not yet moved into a context, each importing from the ones above it here, never from one below:

    contract   what a project file says: places, the profile, stories and epics, the stage table
    state      where a story stands: the journal, the owned files, the story state, the schedule, the claim
    gate       what decides: the checks, their registry, the stamps a passed stage writes
    runner     what the runner asks between stages: its tables, a story's worktree, the skeletons, a request worked
    cli        what a person, a stage or factory.sh asks about the pipeline: status, help, usage, the readers

stdlib only.
"""

import sys


def utf8_streams() -> None:
    """The lines carry `—` and `→`; a Windows console's code page cannot encode `→`, and the print raises. And every
    line ends in `\n` alone: on Windows a text stream writes `\r\n`, and whoever reads the output — the runner,
    factory.sh's `$(…)` — would keep the `\r` on the last field of every line ("plan\r" names no stage)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
