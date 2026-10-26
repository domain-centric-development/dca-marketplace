"""The exact shape the gate holds a stage's hand-over to — from the gate's own constants, for a stage to read."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.hand_over_skeletons import HandOverSkeletons


@dataclasses.dataclass(frozen=True)
class ShowHandOverContractQuery:
    stage: str


class ShowHandOverContractInputPort(UseCase[ShowHandOverContractQuery, typing.Optional[str]], typing.Protocol):
    """The contract's text; None for a name that has none."""


class ShowHandOverContractUseCase:
    def __init__(self, skeletons: HandOverSkeletons) -> None:
        self._skeletons = skeletons

    def execute(self, query: ShowHandOverContractQuery) -> typing.Optional[str]:
        return self._skeletons.contract(query.stage)
