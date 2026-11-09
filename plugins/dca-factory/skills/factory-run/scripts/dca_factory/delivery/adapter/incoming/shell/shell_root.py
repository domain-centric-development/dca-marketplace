"""What `factory.sh`'s command line takes from the composition root — given at start (`wire`), never imported."""

from __future__ import annotations

import typing

from ....application.setup.check_detected_profile import CheckDetectedProfileInputPort
from ....application.setup.install_pipeline import InstallPipelineInputPort
from ....application.setup.refresh_pipeline import RefreshPipelineInputPort
from ....application.setup.write_detected_profile import WriteDetectedProfileInputPort

#: An exit, what was printed, what was said on stderr — or both in their order, where the caller merges them.
Captured = typing.Tuple[int, str, str]


class ShellRoot(typing.Protocol):
    """The cli's and the gate's command lines in this process, the tool table, the pipelines on this machine, and the
    setup's and the update's use cases."""

    #: the Python the script found, by the name it was found under — what reaches the profile and the allow list
    python: str

    def cli(self, argv: typing.Sequence[str]) -> int:
        """The cli's command line, its output passed through; its exit."""
        ...

    def cli_captured(self, argv: typing.Sequence[str], merged: bool = False) -> Captured:
        """The cli's command line, its output kept (stderr after stdout's text where <merged>)."""
        ...

    def gate(self, argv: typing.Sequence[str]) -> int:
        """The project's gate's command line — in this process where it is this package by content, else its own."""
        ...

    def gate_merged(self, argv: typing.Sequence[str]) -> typing.Tuple[int, str]:
        """The same, what it printed and said kept in one text, in their order."""
        ...

    def tool_names(self) -> typing.List[str]: ...

    def tool_skills(self, tool: str) -> str:
        """The project folder <tool> discovers skills in; "" for no tool of that name."""
        ...

    def tool_args(self, tool: str) -> str:
        """The person's extra flags for <tool> (FACTORY_<TOOL>_ARGS)."""
        ...

    def pipeline_found(self) -> typing.Optional[str]:
        """The newest pipeline's skill folder on this machine."""
        ...

    def freshness(self) -> None:
        """Whether the project is behind the pipeline beside it, said."""
        ...

    def profile_renames(self) -> typing.List[str]:
        """The profile's lines that name a renamed skill or key, as "<old line> → <new line>"."""
        ...

    def runner_header(self) -> typing.List[str]:
        """The lines of the script's usage, at its top."""
        ...

    def run(self, argv: typing.Sequence[str]) -> int:
        """The runner itself, in this process (`--run`)."""
        ...

    def set_up(self) -> InstallPipelineInputPort: ...

    def update(self) -> RefreshPipelineInputPort: ...

    def check_detected(self) -> CheckDetectedProfileInputPort: ...

    def write_detected(self) -> WriteDetectedProfileInputPort: ...
