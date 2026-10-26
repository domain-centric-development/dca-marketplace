"""Read one invocation's usage from a tool's raw output — what a session hands the journal for a stage it ran."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.tool_binaries import ToolBinaries


@dataclasses.dataclass(frozen=True)
class ReadToolUsageQuery:
    format: str
    path: str
    model: typing.Optional[str] = None


class ReadToolUsageInputPort(UseCase[ReadToolUsageQuery, typing.List[str]], typing.Protocol):
    """The usage's lines, as the journal takes them."""


class ReadToolUsageUseCase:
    def __init__(self, tools: ToolBinaries) -> None:
        self._tools = tools

    def execute(self, query: ReadToolUsageQuery) -> typing.List[str]:
        return self._tools.usage_lines(query.format, query.path, query.model)
