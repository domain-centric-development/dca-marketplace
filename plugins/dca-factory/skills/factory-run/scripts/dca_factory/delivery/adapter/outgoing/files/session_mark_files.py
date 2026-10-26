"""A session's marks in the story's journal and the person's parts around its stage, through the runner's own
writers."""

from __future__ import annotations

import typing

from .journal_files import journal_writer
from .owned_files import owned_end, record_owned
from .windows import mark_stage, mark_window


class SessionMarkFiles:
    def __init__(self, cwd: str, runs: str) -> None:
        self._cwd, self._runs = cwd, runs

    def window(self, story: str, work: str, edge: str, session_log: typing.Optional[str]) -> int:
        return mark_window(self._cwd, self._runs, story, work, edge, session_log)

    def stage(self, story: str, stage: str, edge: str, session_log: typing.Optional[str]) -> int:
        return mark_stage(self._cwd, self._runs, story, stage, edge, session_log)

    def record_owned(self, story: str) -> None:
        record_owned(self._runs, story)

    def compare_owned(self, story: str, stage: str, ran: int) -> int:
        return owned_end(self._runs, story, stage, str(ran))

    def append(self, story: str, lines: str) -> None:
        journal_writer(self._runs, story).write(lines)
