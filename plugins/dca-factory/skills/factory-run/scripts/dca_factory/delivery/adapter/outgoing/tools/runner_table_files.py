"""The tool table as the runner's assignments, and the places as the profile sets them."""

from __future__ import annotations

import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from .agents import tools_shell
from ....application.shared.runner_tables import RunnerTables


class RunnerTableFiles(RunnerTables):
    def tool_lines(self) -> typing.Optional[typing.List[str]]:
        return tools_shell()

    def place(self, key: str) -> str:
        return place(key)
