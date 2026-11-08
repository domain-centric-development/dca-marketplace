"""Deliver a story the gate holds: built or adopted, every check passed."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.story import Delivery, StoryId
from ..shared.story_repository import StoryRepository


@dataclasses.dataclass(frozen=True)
class DeliverStoryCommand:
    story: StoryId
    at: Moment


@dataclasses.dataclass(frozen=True)
class DeliveredByGate:
    """Delivered, by the gate, on this moment."""

    delivery: Delivery


class DeliverStoryInputPort(UseCase[DeliverStoryCommand, DeliveredByGate], typing.Protocol):
    """Deliver a story the gate holds."""


class DeliverStoryUseCase(DeliverStoryInputPort):
    """The story says delivered, by the gate — the aggregate refuses a story that was never released, is superseded or
    is delivered already; the save and its event in one transaction."""

    def __init__(self, stories: StoryRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._stories = stories
        self._events = events
        self._transactions = transactions

    def execute(self, command: DeliverStoryCommand) -> DeliveredByGate:
        story = self._stories.get(command.story)
        delivery = story.deliver_by_gate(command.at)

        def save() -> None:
            self._stories.save(story)
            self._events.publish_and_clear_events(story)

        self._transactions.in_transaction(save)
        return DeliveredByGate(delivery)
