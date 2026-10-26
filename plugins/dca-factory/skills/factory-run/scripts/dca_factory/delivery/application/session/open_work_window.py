"""Open a work window on a story outside a stage — the backlog's or the decisions' — so the session's tokens and time count on it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.session_marks import SessionMarks


@dataclasses.dataclass(frozen=True)
class OpenWorkWindowCommand:
    story: str
    work: str
    session_log: typing.Optional[str] = None


class OpenWorkWindowInputPort(UseCase[OpenWorkWindowCommand, int], typing.Protocol):
    """Its exit."""


class OpenWorkWindowUseCase:
    def __init__(self, port: SessionMarks) -> None:
        self._port = port

    def execute(self, command: OpenWorkWindowCommand) -> int:
        return self._port.window(command.story, command.work, "start", command.session_log)
