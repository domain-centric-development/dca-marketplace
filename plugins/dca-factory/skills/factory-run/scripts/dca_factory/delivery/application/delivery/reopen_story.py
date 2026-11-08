"""Take a delivered story back for a correction a person gave on looking at it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.decision_record import RecordId
from ...domain.model.moment import Moment
from ...domain.model.story import CitedCorrection, StoryId
from ...domain.model.story_words import Detail
from ..shared.acceptances import Acceptances
from ..shared.story_repository import StoryRepository
from ..shared.story_runs import StoryRuns


@dataclasses.dataclass(frozen=True)
class ReopenStoryCommand:
    story: StoryId
    at: Moment


@dataclasses.dataclass(frozen=True)
class Reopened:
    """Taken back for the record; the delivered pass kept where `kept` says ("" without a run folder)."""

    record: RecordId
    kept: str


@dataclasses.dataclass(frozen=True)
class NoCorrection:
    """No acceptance record answered with a correction."""


@dataclasses.dataclass(frozen=True)
class CheckoutHeld:
    """Other stories hold the checkout with unfinished code — one story at a time."""

    holders: typing.Tuple[StoryId, ...]


@dataclasses.dataclass(frozen=True)
class NotCited:
    """The correction is not written into the story."""

    record: RecordId


@dataclasses.dataclass(frozen=True)
class NewWish:
    """After an acceptance the correction changes accepted criteria — a new story, not this one reopened."""

    changed: typing.Tuple[str, ...]


ReopenStoryResult = typing.Union[Reopened, NoCorrection, CheckoutHeld, NotCited, NewWish]


class ReopenStoryInputPort(UseCase[ReopenStoryCommand, ReopenStoryResult], typing.Protocol):
    """Take a delivered story back for a correction."""


class ReopenStoryUseCase(ReopenStoryInputPort):
    """Only with an answered acceptance record the story cites — the answer is in the story, not in a prompt. Before
    a story was accepted every answer is a correction; after an acceptance, one that changes a criterion as accepted
    is a new wish. The pass the story ran is kept aside, and the story runs again from plan."""

    def __init__(self, stories: StoryRepository, acceptances: Acceptances, runs: StoryRuns,
                 events: DomainEventPublisher, transactions: TransactionBoundary) -> None:
        self._events = events
        self._transactions = transactions
        self._stories = stories
        self._acceptances = acceptances
        self._runs = runs

    def execute(self, command: ReopenStoryCommand) -> ReopenStoryResult:
        story = self._stories.get(command.story)
        record = self._acceptances.correction_of(story.id)
        if record is None:
            return NoCorrection()
        holders = tuple(self._runs.holding_checkout(story.id))
        if holders:
            return CheckoutHeld(holders)
        if not self._acceptances.cited(story.id, record):
            return NotCited(record)
        changed = tuple(self._acceptances.changed_since_accepted(story.id))
        if changed:
            return NewWish(changed)
        story.reopen(CitedCorrection(Detail(record.value)), command.at)
        kept = self._runs.keep_pass(story.id)

        def save() -> None:
            self._stories.save(story)
            self._events.publish_and_clear_events(story)

        self._transactions.in_transaction(save)
        return Reopened(record, kept)
