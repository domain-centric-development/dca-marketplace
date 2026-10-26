"""Start a stage a session carries out itself: marked in the story's journal, the person's parts recorded."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.session_marks import SessionMarks


@dataclasses.dataclass(frozen=True)
class StartSessionStageCommand:
    story: str
    stage: str
    session_log: typing.Optional[str] = None


class StartSessionStageInputPort(UseCase[StartSessionStageCommand, int], typing.Protocol):
    """Its exit."""


class StartSessionStageUseCase:
    def __init__(self, port: SessionMarks) -> None:
        self._port = port

    def execute(self, command: StartSessionStageCommand) -> int:
        code = self._port.stage(command.story, command.stage, "start", command.session_log)
        if code == 0:
            self._port.record_owned(command.story)
        return code
