"""Check parity: every implementation's reports prove every mandatory scenario of one scenario contract."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.verdict import Findings
from ...domain.service.change_checks import ChangeChecks
from ..shared.parity_reports import ParityReports


@dataclasses.dataclass(frozen=True)
class CheckParityCommand:
    """The parity config: `scenarios:` and one `implementation.<name>:` line per implementation."""

    config: str


class CheckParityInputPort(UseCase[CheckParityCommand, Findings], typing.Protocol):
    """Check parity."""


class CheckParityUseCase:
    """Every implementation's reports against one scenario contract (`ChangeChecks.parity`)."""

    def __init__(self, reports: ParityReports) -> None:
        self._reports = reports

    def execute(self, command: CheckParityCommand) -> Findings:
        return ChangeChecks.parity(self._reports.facts(command.config))
