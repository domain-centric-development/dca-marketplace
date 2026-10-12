"""The factory's pipeline as one package — `story-gate.py` and `factory-cli.py` beside it are its entry points.

    contract   what a project file says: places, front matter, profile, stories, decisions, the stage table
    reports    what a run left to read: test reports, a command's outcome, tree snapshots, a tool's usage
    state      where a story stands: the journal, the owned files, the story state, the schedule, the claim
    spec       what holds: the living spec per context, the story's criteria as entries, the delta, the merge
    gate       what decides: the checks, their registry, the stamps a passed stage writes
    tools      an agent tool as a record, probed once against its binary
    runner     what the runner asks between stages: its tables, a story's worktree, the skeletons
    cli        what a person, a stage or factory.sh asks about the pipeline: status, help, usage, the readers

Each module imports from the ones above it in this list, never from one below. stdlib only.
"""

import sys


def utf8_streams():
    """The lines carry `—` and `→`; a Windows console's code page cannot encode `→`, and the print raises. And every
    line ends in `\n` alone: on Windows a text stream writes `\r\n`, and whoever reads the output — the runner,
    factory.sh's `$(…)` — would keep the `\r` on the last field of every line ("plan\r" names no stage)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
