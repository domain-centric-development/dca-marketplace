"""Split off the scenarios of a released story the plan found holding on today's code."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.stage_story import PlanAdoption
from ...domain.model.story import StoryId
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class SplitOffOnPlanCommand:
    story: StoryId
    adoption: PlanAdoption
    at: Moment


@dataclasses.dataclass(frozen=True)
class SplitOffOnPlan:
    """The adopted story the scenarios moved into."""

    into: StoryId


class SplitOffOnPlanInputPort(UseCase[SplitOffOnPlanCommand, SplitOffOnPlan], typing.Protocol):
    """Split off what holds."""


class SplitOffOnPlanUseCase(SplitOffOnPlanInputPort):
    """The story splits off what holds into an adopted story, by its aggregate — released ones only; the new story is
    added first, from the scenarios as the story still says them, then the story is saved without them, each with its
    events, in one transaction: one decision of the plan."""

    def __init__(self, stories: StoryRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._stories = stories
        self._events = events
        self._transactions = transactions

    def execute(self, command: SplitOffOnPlanCommand) -> SplitOffOnPlan:
        story = self._stories.get(command.story)
        split = story.split_off(command.adoption.keys(), command.adoption.held(), command.at)

        def save() -> None:
            self._stories.save(split)
            self._stories.save(story)
            self._events.publish_and_clear_events(split)
            self._events.publish_and_clear_events(story)

        self._transactions.in_transaction(save)
        return SplitOffOnPlan(split.id)
