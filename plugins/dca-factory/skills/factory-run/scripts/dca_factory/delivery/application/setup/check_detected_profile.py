"""What detection finds against the stack profile — read-only in every state. A detected key the profile lacks is a
finding; a value that differs from detection is a person's decision and only a note, because a check that goes red on
a decision gets switched off."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.pipeline_install import PipelineInstall, ProfileOutcome, Proposal


@dataclasses.dataclass(frozen=True)
class CheckDetectedProfile:
    proposal: Proposal


class CheckDetectedProfileInputPort(UseCase[CheckDetectedProfile, ProfileOutcome], typing.Protocol):
    """The profile against detection."""


class CheckDetectedProfileUseCase(CheckDetectedProfileInputPort):
    def __init__(self, install_port: PipelineInstall) -> None:
        self._port = install_port

    def execute(self, command: CheckDetectedProfile) -> ProfileOutcome:
        return self._port.check_detected(command.proposal)
