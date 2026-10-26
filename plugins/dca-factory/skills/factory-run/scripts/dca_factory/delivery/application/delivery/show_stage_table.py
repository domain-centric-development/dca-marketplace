"""The stage table as the runner and the cli read it: the run order, the steps after it, what each shared process
carries, which gate runs before and which after its stage, which stages run the mapped tests without the suite,
which work under the guard, which kind runs which row, the hand-over each writes — and, for the shell runner, the
tool table and the places it asks for."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.stage import PIPELINE, StoryKind, Trait
from ..shared.runner_tables import RunnerTables

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowStageTableQuery:
    places: typing.Tuple[str, ...] = ()
    with_tools: bool = False


class ShowStageTableInputPort(UseCase[ShowStageTableQuery, Model], typing.Protocol):
    """The table's lists by name; `tools` (None where a record is no word) and `places` where asked."""


class ShowStageTableUseCase:
    def __init__(self, tables: RunnerTables) -> None:
        self._tables = tables

    def execute(self, query: ShowStageTableQuery) -> Model:
        in_order = [s for s in PIPELINE if Trait.IN_ORDER in s.traits]
        windows: typing.Dict[str, typing.List[str]] = {}
        for stage in PIPELINE:
            if stage.window:
                windows.setdefault(stage.window.value, []).append(stage.name.value)
        return dict(
            order=[s.name.value for s in in_order],
            steps=[s.name.value for s in PIPELINE if Trait.IN_ORDER not in s.traits],
            rows=[dict(name=s.name.value, window=s.window.value if s.window else "",
                       in_order=Trait.IN_ORDER in s.traits) for s in PIPELINE],
            windows=windows,
            pre_gated=[s.name.value for s in in_order if Trait.GATED in s.traits and Trait.POST_GATED not in s.traits],
            post_gated=[s.name.value for s in in_order if Trait.POST_GATED in s.traits],
            red=[s.name.value for s in in_order if Trait.TESTED in s.traits and Trait.SUITE not in s.traits],
            guarded=[s.name.value for s in PIPELINE if Trait.GUARDED in s.traits],
            kinds=[(kind.value, s.name.value) for s in PIPELINE for kind in StoryKind if kind in s.kinds],
            files={s.name.value: s.hand_over.value for s in in_order if s.hand_over},
            tools=self._tables.tool_lines() if query.with_tools else [],
            places={key: self._tables.place(key) for key in query.places})
