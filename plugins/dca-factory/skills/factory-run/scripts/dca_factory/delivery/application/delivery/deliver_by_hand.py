"""Deliver a story a person built."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.moment import Moment
from ...domain.model.person import Person
from ...domain.model.story import Delivery, StoryId
from ..shared.story_claims import ClaimHeld, StoryClaims
from ..shared.story_journal import StoryJournal
from ..shared.story_repository import StoryRepository
from ..shared.story_spec import SpecChange, StorySpec


@dataclasses.dataclass(frozen=True)
class DeliverByHandCommand:
    story: StoryId
    by: Person
    at: Moment
    #: delivers it over another factory's claim
    force: bool


@dataclasses.dataclass(frozen=True)
class DeliveredByHand:
    """Delivered, claimed; the new criteria taken into the spec unproven; where the story's file is."""

    delivery: Delivery
    unproven: SpecChange
    where: str


@dataclasses.dataclass(frozen=True)
class ClaimedElsewhere:
    """Another factory builds the story."""

    claim: ClaimHeld


@dataclasses.dataclass(frozen=True)
class ChangesWhatHolds:
    """The story changes what holds: the delta of a change is planned, not taken by hand."""

    change: SpecChange


DeliverByHandResult = typing.Union[DeliveredByHand, ClaimedElsewhere, ChangesWhatHolds]


class DeliverByHandInputPort(UseCase[DeliverByHandCommand, DeliverByHandResult], typing.Protocol):
    """Deliver a story by hand."""


class DeliverByHandUseCase:
    """A story a person built is delivered, claimed by them — works where the factory never ran; `--prove` checks it
    later. Its new criteria go into the spec without a test line. A story another factory claimed is delivered only
    with force, and that is journaled; one that changes what holds is not delivered by hand."""

    def __init__(self, stories: StoryRepository, claims: StoryClaims, spec: StorySpec,
                 journal: StoryJournal) -> None:
        self._stories = stories
        self._claims = claims
        self._spec = spec
        self._journal = journal

    def execute(self, command: DeliverByHandCommand) -> DeliverByHandResult:
        story = self._stories.get(command.story)
        delivery = story.deliver_by_hand(command.by, command.at)
        held = self._claims.held_elsewhere(story.id)
        if held is not None:
            if not command.force:
                return ClaimedElsewhere(held)
            self._journal.delivered_over_claim(story.id, held.who)
        changing = self._spec.changing(story.id)
        if changing.keys:
            return ChangesWhatHolds(changing)
        self._stories.save(story)
        return DeliveredByHand(delivery, self._spec.take_unproven(story.id), self._stories.path_of(story.id))
