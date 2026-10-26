"""Move an older layout to one owner per place — what `factory.sh update` runs once; a second run moves nothing."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.project_upkeep import ProjectUpkeep


@dataclasses.dataclass(frozen=True)
class MigrateLayoutCommand:
    """No field: the project is the one the pipeline runs in."""


class MigrateLayoutInputPort(UseCase[MigrateLayoutCommand, int], typing.Protocol):
    """Its exit."""


class MigrateLayoutUseCase:
    def __init__(self, upkeep: ProjectUpkeep) -> None:
        self._upkeep = upkeep

    def execute(self, command: MigrateLayoutCommand) -> int:
        return self._upkeep.migrate()
