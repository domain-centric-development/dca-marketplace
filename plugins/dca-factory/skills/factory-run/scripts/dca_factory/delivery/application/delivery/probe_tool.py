"""Probe a tool's binary against its record: a flag a stage needs that the help does not name fails every stage started
with it; an isolation flag it lacks only lets the tool's own setup in."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import UseCase
from ..shared.tool_binaries import Probe, ToolBinaries


class Probed(enum.Enum):
    UNKNOWN = "unknown"             # no record by that name
    NOT_INSTALLED = "not-installed"  # its binary is not on the PATH
    PROBED = "probed"


@dataclasses.dataclass(frozen=True)
class ProbeToolQuery:
    tool: str


@dataclasses.dataclass(frozen=True)
class ToolProbe:
    outcome: Probed
    binary: str = ""
    found: typing.Optional[Probe] = None
    known: typing.Tuple[str, ...] = ()


class ProbeToolInputPort(UseCase[ProbeToolQuery, ToolProbe], typing.Protocol):
    """The probe's outcome."""


class ProbeToolUseCase:
    def __init__(self, tools: ToolBinaries) -> None:
        self._tools = tools

    def execute(self, query: ProbeToolQuery) -> ToolProbe:
        known = tuple(self._tools.names())
        if query.tool not in known:
            return ToolProbe(Probed.UNKNOWN, known=known)
        found = self._tools.probe(query.tool)
        if found is None:
            return ToolProbe(Probed.NOT_INSTALLED, self._tools.binary(query.tool))
        return ToolProbe(Probed.PROBED, found.binary, found)
