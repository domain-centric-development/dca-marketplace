"""The agent tools as installed on this machine: which the factory knows, what each binary's help names, what one of
its raw outputs says it used."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort


@dataclasses.dataclass(frozen=True)
class Probe:
    """The tool's binary, and the flags its record passes that the binary's help does not name: one a stage needs
    (`required`), an isolation flag the runner leaves out (`isolation`)."""

    binary: str
    required: typing.Tuple[str, ...]
    isolation: typing.Tuple[str, ...]


class ToolBinaries(OutputPort, typing.Protocol):
    def names(self) -> typing.Sequence[str]:
        """The tools the factory has a record of."""
        ...

    def binary(self, tool: str) -> str:
        """The program its record starts."""
        ...

    def probe(self, tool: str) -> typing.Optional[Probe]:
        """What its binary's help lacks; None where the binary is not on the PATH."""
        ...

    def usage_lines(self, fmt: str, path: str, model: typing.Optional[str]) -> typing.List[str]:
        """One invocation's usage, read from a tool's raw output in <fmt> (claude-json, codex-jsonl, opencode-json)."""
        ...
