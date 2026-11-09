"""Adopt a released story whose every scenario the plan found holding on today's code."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.plan_facts import PlanAdoption
from ...domain.model.story import PLAN_ADOPT, Assumption, StoryId
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class AdoptOnPlanCommand:
    story: StoryId
    adoption: PlanAdoption
    at: Moment


@dataclasses.dataclass(frozen=True)
class AdoptedOnPlan:
    """Adopted: the runner goes on with the adoption."""

    story: StoryId


class AdoptOnPlanInputPort(UseCase[AdoptOnPlanCommand, AdoptedOnPlan], typing.Protocol):
    """Adopt a story the plan found holding as a whole."""


class AdoptOnPlanUseCase(AdoptOnPlanInputPort):
    """The story is adopted through its aggregate — released ones only —, the plan's finding its answered line; the
    save and its event in one transaction."""

    def __init__(self, stories: StoryRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._stories = stories
        self._events = events
        self._transactions = transactions

    def execute(self, command: AdoptOnPlanCommand) -> AdoptedOnPlan:
        story = self._stories.get(command.story)
        story.adopt_on_plan(Assumption.answered(command.adoption.whole(), PLAN_ADOPT), command.at)

        def save() -> None:
            self._stories.save(story)
            self._events.publish_and_clear_events(story)

        self._transactions.in_transaction(save)
        return AdoptedOnPlan(story.id)
