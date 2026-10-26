"""What the stages' and requests' processes wrote while they ran — their raw output, read as lines a person follows."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import Store


@dataclasses.dataclass(frozen=True)
class Output:
    """One process's output: the story (or request) it ran for, the stage or process, its file as shown."""

    name: str
    stage: str
    path: str


class StageOutputs(Store, typing.Protocol):
    def outputs(self, story: str, process: typing.Optional[str]) -> typing.Sequence[Output]:
        """One story's outputs in the order they began, or one process's alone."""
        ...

    def newest(self, story: typing.Optional[str], process: typing.Optional[str],
               request: typing.Optional[str]) -> typing.Optional[Output]:
        """The newest output — of a request, one story, or every story — None before any."""
        ...

    def read(self, output: Output, offset: int) -> typing.Tuple[str, int]:
        """The text written from <offset> on, and the offset after it; '' where the file is gone."""
        ...

    def lines(self, text: str) -> typing.Tuple[typing.List[str], bool]:
        """A tool's stream as the lines a person reads, and whether it reports its end."""
        ...
