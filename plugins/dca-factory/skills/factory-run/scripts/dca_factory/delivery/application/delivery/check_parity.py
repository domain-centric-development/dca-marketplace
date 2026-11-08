"""Check parity: every implementation's reports prove every mandatory scenario of one scenario contract."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.verdict import Findings
from ..shared.parity_reports import ParityReports
from .pipeline_rules import decides


@dataclasses.dataclass(frozen=True)
class CheckParityCommand:
    """The parity config: `scenarios:` and one `implementation.<name>:` line per implementation."""

    config: str


class CheckParityInputPort(UseCase[CheckParityCommand, Findings], typing.Protocol):
    """Check parity."""


class CheckParityUseCase:
    """Every implementation's reports against one scenario contract (`ParityFacts.findings`)."""

    def __init__(self, reports: ParityReports) -> None:
        self._reports = reports

    @decides("GATE-IMPLEMENTATIONS")
    def execute(self, command: CheckParityCommand) -> Findings:
        return self._reports.facts(command.config).findings()
