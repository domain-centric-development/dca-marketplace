"""The run's lines on the runner's terminal: what it does on stdout, what stopped on stderr, in the order they came."""

from __future__ import annotations

import sys


class ConsoleLines:
    """`RunLines` on the process's own streams."""

    def out(self, line: str) -> None:
        print(line, flush=True)

    def err(self, line: str) -> None:
        sys.stdout.flush()
        print(line, file=sys.stderr, flush=True)
