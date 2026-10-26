"""How a run ends early: a signal arrived or what it stands on changed — the exit it ends with. Any port of a run may
raise it between two steps; the runner's entry point turns it into the exit code."""

from __future__ import annotations

#: The exits of the signals that end a run: a TERM, a hang-up, an interrupt.
SIGNAL_EXITS = {"SIGTERM": 143, "SIGHUP": 129, "SIGINT": 130}


class Stopped(Exception):
    """The run ends here with this exit code — the pipeline changed under it, a signal arrived."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code
