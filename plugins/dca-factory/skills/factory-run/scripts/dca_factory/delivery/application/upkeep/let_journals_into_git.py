"""Let the story journals into git — the record of how a story was delivered travels with the project — while the rest
of the pipeline's folder stays out."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.project_upkeep import ProjectUpkeep


@dataclasses.dataclass(frozen=True)
class LetJournalsIntoGitCommand:
    """No field: the project is the one the pipeline runs in."""


class LetJournalsIntoGitInputPort(UseCase[LetJournalsIntoGitCommand, typing.Optional[str]], typing.Protocol):
    """Where the journals are when the ignores changed, else None."""


class LetJournalsIntoGitUseCase:
    def __init__(self, upkeep: ProjectUpkeep) -> None:
        self._upkeep = upkeep

    def execute(self, command: LetJournalsIntoGitCommand) -> typing.Optional[str]:
        return self._upkeep.journals_into_git()
