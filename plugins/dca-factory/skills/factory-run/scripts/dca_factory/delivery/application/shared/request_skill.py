"""A request's skill run headless by a tool: its prompt, its process, its usage booked to the request."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from .requests import Kind, Request


@dataclasses.dataclass(frozen=True)
class SkillRun:
    """How the tool ended: its exit, whether its time limit stopped it, and where its output is kept."""

    code: int
    timed_out: bool
    output: str


class RequestSkill(OutputPort, typing.Protocol):
    """The tools a request's skill runs with."""

    def tool_for(self, unit: str, given: str) -> str:
        """The tool a request's unit runs with: the profile's choice, else the run's."""
        ...

    def known(self, tool: str) -> bool:
        """Whether the tool can be started — a known tool, or the person's own command."""
        ...

    def run(self, request: Request, kind: Kind, unit: str, tool: str) -> SkillRun:
        """The skill run for the request, its usage journaled and booked to it. Stopped from outside, it raises."""
        ...
