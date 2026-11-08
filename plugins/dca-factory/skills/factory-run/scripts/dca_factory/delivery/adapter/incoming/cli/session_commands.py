"""The session feature's commands of the cli: a window of work and a stage run by hand opened and closed, a line
for the story's journal."""

from __future__ import annotations

import typing

from ....application.session.append_journal import AppendJournalCommand
from ....application.session.close_work_window import CloseWorkWindowCommand
from ....application.session.end_session_stage import EndSessionStageCommand
from ....application.session.open_work_window import OpenWorkWindowCommand
from ....application.session.start_session_stage import StartSessionStageCommand
from . import root


def open_window(cwd: str, runs: str, story: str, window: str, log: typing.Optional[str]) -> int:
    return root.wiring.open_work_window(cwd, runs).execute(OpenWorkWindowCommand(story, window, log))


def close_window(cwd: str, runs: str, story: str, window: str, log: typing.Optional[str]) -> int:
    return root.wiring.close_work_window(cwd, runs).execute(CloseWorkWindowCommand(story, window, log))


def start_stage(cwd: str, runs: str, story: str, stage: str, log: typing.Optional[str]) -> int:
    return root.wiring.start_session_stage(cwd, runs).execute(StartSessionStageCommand(story, stage, log))


def end_stage(cwd: str, runs: str, story: str, stage: str, log: typing.Optional[str]) -> int:
    return root.wiring.end_session_stage(cwd, runs).execute(EndSessionStageCommand(story, stage, log))


def append_journal(cwd: str, runs: str, line: str, text: str) -> int:
    return root.wiring.append_journal(cwd, runs).execute(AppendJournalCommand(line, text))
