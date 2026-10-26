"""Append lines a process hands over to a story's journal, each numbered."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.session_marks import SessionMarks


@dataclasses.dataclass(frozen=True)
class AppendJournalCommand:
    story: str
    lines: str


class AppendJournalInputPort(UseCase[AppendJournalCommand, int], typing.Protocol):
    """Its exit."""


class AppendJournalUseCase:
    def __init__(self, port: SessionMarks) -> None:
        self._port = port

    def execute(self, command: AppendJournalCommand) -> int:
        self._port.append(command.story, command.lines)
        return 0
