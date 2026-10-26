"""What a stage's process does, as lines: every process of a story, or the newest output alone with its last lines."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.stage_outputs import StageOutputs

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowStageOutputsQuery:
    """`every`: every process of `story` in the order they began; else the newest output (of `request`, `story` or
    any) with its last `lines` lines (0: all)."""

    story: typing.Optional[str] = None
    process: typing.Optional[str] = None
    request: typing.Optional[str] = None
    every: bool = False
    lines: int = 0


class ShowStageOutputsInputPort(UseCase[ShowStageOutputsQuery, typing.List[Model]], typing.Protocol):
    """One entry per output: `story`, `stage`, `file`, `running`, `lines`."""


class ShowStageOutputsUseCase:
    def __init__(self, outputs: StageOutputs) -> None:
        self._outputs = outputs

    def execute(self, query: ShowStageOutputsQuery) -> typing.List[Model]:
        if query.every:
            found = list(self._outputs.outputs(query.story or "", query.process))
        else:
            newest = self._outputs.newest(query.story, query.process, query.request)
            found = [newest] if newest else []
        entries = []
        for output in found:
            lines, ended = self._outputs.lines(self._outputs.read(output, 0)[0])
            if not query.every and query.lines > 0:
                lines = lines[-query.lines:]
            entries.append(dict(story=output.name, stage=output.stage, file=output.path, running=not ended,
                                lines=lines))
        return entries
