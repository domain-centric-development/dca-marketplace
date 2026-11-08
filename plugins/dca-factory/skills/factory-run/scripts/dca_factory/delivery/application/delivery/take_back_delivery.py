"""Take a published story's delivery back on its branch, so it is delivered again on the main line as it is now."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.story import StoryId
from ..shared.published_branches import PublishedBranches, TakenBack


@dataclasses.dataclass(frozen=True)
class TakeBackDeliveryCommand:
    story: StoryId
    at: Moment


class TakeBackDeliveryInputPort(UseCase[TakeBackDeliveryCommand, typing.Optional[TakenBack]], typing.Protocol):
    """Take a published delivery back; None where the story has no published branch."""


class TakeBackDeliveryUseCase(TakeBackDeliveryInputPort):
    """A published branch whose merge request lost the race goes back to before its delivery, so the integrate step
    merges the remote main line and the delivering gate merges again under the new rules. The spec is never resolved
    by text; the story is taken back by its aggregate on the branch, the save and its event in one transaction, then
    the branch is committed."""

    def __init__(self, branches: PublishedBranches, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._branches = branches
        self._events = events
        self._transactions = transactions

    def execute(self, command: TakeBackDeliveryCommand) -> typing.Optional[TakenBack]:
        if not self._branches.published(command.story):
            return None
        stories = self._branches.stories(command.story)
        story = stories.get(command.story)
        story.take_back_publication(self._branches.published_over(command.story), command.at)
        taken = self._branches.set_back_spec(command.story)

        def save() -> None:
            stories.save(story)
            self._events.publish_and_clear_events(story)

        self._transactions.in_transaction(save)
        self._branches.commit_taken_back(command.story, taken)
        return taken
