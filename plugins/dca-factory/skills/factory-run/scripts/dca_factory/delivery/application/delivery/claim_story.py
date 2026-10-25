"""Claim one story on the remote, so no other factory builds it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.story import StoryId
from ..shared.story_claims import ClaimOutcome, StoryClaims
from ..shared.story_journal import StoryJournal


@dataclasses.dataclass(frozen=True)
class ClaimStoryCommand:
    story: StoryId


class ClaimStoryInputPort(UseCase[ClaimStoryCommand, ClaimOutcome], typing.Protocol):
    """Claim a story across factories."""


class ClaimStoryUseCase:
    """The claim on the remote the profile names; a story another factory holds is noted in its journal."""

    def __init__(self, claims: StoryClaims, journal: StoryJournal) -> None:
        self._claims = claims
        self._journal = journal

    def execute(self, command: ClaimStoryCommand) -> ClaimOutcome:
        outcome = self._claims.claim(command.story)
        if outcome.held is not None:
            self._journal.claimed_elsewhere(command.story, outcome.held)
        return outcome
