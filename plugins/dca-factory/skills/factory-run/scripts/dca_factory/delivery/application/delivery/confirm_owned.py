"""The person's word that the story and its answers are as they want them after a stage changed them."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.story import StoryId
from ..shared.owned_changes import OwnedChanges
from ..shared.story_journal import StoryJournal


@dataclasses.dataclass(frozen=True)
class ConfirmOwnedCommand:
    story: StoryId


@dataclasses.dataclass(frozen=True)
class Confirmed:
    parts: typing.Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class NothingToConfirm:
    """No stage changed the story or an answer."""


ConfirmOwnedResult = typing.Union[Confirmed, NothingToConfirm]


class ConfirmOwnedInputPort(UseCase[ConfirmOwnedCommand, ConfirmOwnedResult], typing.Protocol):
    """Confirm what a stage changed as the person's."""


class ConfirmOwnedUseCase:
    """The mark goes, what changed is journaled, and the story runs on from what its files say."""

    def __init__(self, owned: OwnedChanges, journal: StoryJournal) -> None:
        self._owned = owned
        self._journal = journal

    def execute(self, command: ConfirmOwnedCommand) -> ConfirmOwnedResult:
        parts = tuple(self._owned.changed(command.story))
        if not parts:
            return NothingToConfirm()
        self._owned.clear(command.story)
        self._journal.owned_confirmed(command.story, parts)
        return Confirmed(parts)
