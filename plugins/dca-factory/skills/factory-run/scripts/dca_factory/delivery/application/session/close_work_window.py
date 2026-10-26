"""Close a story's work window: what the session used since it opened counts on the story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.session_marks import SessionMarks


@dataclasses.dataclass(frozen=True)
class CloseWorkWindowCommand:
    story: str
    work: str
    session_log: typing.Optional[str] = None


class CloseWorkWindowInputPort(UseCase[CloseWorkWindowCommand, int], typing.Protocol):
    """Its exit."""


class CloseWorkWindowUseCase:
    def __init__(self, port: SessionMarks) -> None:
        self._port = port

    def execute(self, command: CloseWorkWindowCommand) -> int:
        return self._port.window(command.story, command.work, "end", command.session_log)
