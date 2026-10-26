"""End a stage a session carried out: marked with what it used, the person's parts compared — a stage that changed them stops the story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.session_marks import SessionMarks


@dataclasses.dataclass(frozen=True)
class EndSessionStageCommand:
    story: str
    stage: str
    session_log: typing.Optional[str] = None


class EndSessionStageInputPort(UseCase[EndSessionStageCommand, int], typing.Protocol):
    """Its exit."""


class EndSessionStageUseCase:
    def __init__(self, port: SessionMarks) -> None:
        self._port = port

    def execute(self, command: EndSessionStageCommand) -> int:
        code = self._port.stage(command.story, command.stage, "end", command.session_log)
        return self._port.compare_owned(command.story, command.stage, code) or code
