"""Add what detection finds and the stack profile lacks; never overwrite a value a person wrote, except the one key the
person names. The carriers a written line names and Claude Code's allow list follow the profile."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.pipeline_install import PipelineInstall, ProfileOutcome


@dataclasses.dataclass(frozen=True)
class WriteDetectedProfile:
    replace: typing.Optional[str] = None


class WriteDetectedProfileInputPort(UseCase[WriteDetectedProfile, ProfileOutcome], typing.Protocol):
    """The profile after the write, against detection."""


class WriteDetectedProfileUseCase(WriteDetectedProfileInputPort):
    def __init__(self, install_port: PipelineInstall) -> None:
        self._port = install_port

    def execute(self, command: WriteDetectedProfile) -> ProfileOutcome:
        return self._port.write_detected(command.replace)
