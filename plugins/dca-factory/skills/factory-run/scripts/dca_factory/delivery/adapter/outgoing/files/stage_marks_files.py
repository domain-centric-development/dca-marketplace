"""A gate run's marks as files: the judge's signal in the journal, the runner's suites record in the evidence."""

from __future__ import annotations

import os

from ..pipeline.stage_rows import order_for
from ..stack import commands
from ..stack.commands import open_suites_record
from .run_marks import current_stage_files
from .signals import record_judge_signal


class StageMarkFiles:
    """The marks of a gate run over a story of the kind <kind>, in the project <cwd> with its run folder <runs>."""

    def __init__(self, cwd: str, runs: str, kind: str) -> None:
        self._cwd = cwd
        self._runs = runs
        self._kind = kind

    def judge_passed(self, story: str) -> None:
        record_judge_signal(self._runs, story, current_stage_files(self._runs, story, order_for(self._kind))["judge"])

    def record_suites(self, story: str) -> bool:
        key = os.environ.get("FACTORY_SUITES_KEY", "")
        if not key:
            return False
        commands.SUITES_RECORD = open_suites_record(self._cwd, self._runs, story, key)
        return True
