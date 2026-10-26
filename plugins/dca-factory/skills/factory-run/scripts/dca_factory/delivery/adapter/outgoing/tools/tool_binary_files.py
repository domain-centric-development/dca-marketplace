"""The tools' records against the binaries on the PATH, and the stream readers for their raw outputs."""

from __future__ import annotations

import typing

from ....application.shared.tool_binaries import Probe
from .agents import TOOL, unprobed_flags
from .streams import usage_lines


class ToolBinaryFiles:
    def names(self) -> typing.Sequence[str]:
        return list(TOOL)

    def binary(self, tool: str) -> str:
        return TOOL[tool].help[0]

    def probe(self, tool: str) -> typing.Optional[Probe]:
        found = unprobed_flags(TOOL[tool])
        if found is None:
            return None
        required, isolation = found
        return Probe(TOOL[tool].help[0], tuple(required), tuple(isolation))

    def usage_lines(self, fmt: str, path: str, model: typing.Optional[str]) -> typing.List[str]:
        return list(usage_lines(fmt, path, model))
