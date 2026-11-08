"""Hand a claimed delivery to the adopt path, which proves it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.story import Delivery, GatePass, StoryId
from ..shared.story_repository import StoryRepository
from ..shared.story_runs import StoryRuns
from .reopen_story import CheckoutHeld


@dataclasses.dataclass(frozen=True)
class ProveDeliveryCommand:
    story: StoryId
    at: Moment


@dataclasses.dataclass(frozen=True)
class AdoptedForProof:
    """The story is adopted; the claim kept where `claim_kept` says, the earlier pass where `kept` does ("" none)."""

    claim: Delivery
    claim_kept: str
    kept: str


ProveDeliveryResult = typing.Union[AdoptedForProof, CheckoutHeld]


class ProveDeliveryInputPort(UseCase[ProveDeliveryCommand, ProveDeliveryResult], typing.Protocol):
    """Check a claimed delivery through the adopt path."""


class ProveDeliveryUseCase(ProveDeliveryInputPort):
    """The story becomes adopted — the code exists, check it, build nothing — and its claim is kept as a line of its
    evidence. The adopt gate then maps every criterion to a green test and delivers it by the gate. Not the way to
    deliver an edit: a change is a new story."""

    def __init__(self, stories: StoryRepository, runs: StoryRuns,
                 events: DomainEventPublisher, transactions: TransactionBoundary) -> None:
        self._events = events
        self._transactions = transactions
        self._stories = stories
        self._runs = runs

    def execute(self, command: ProveDeliveryCommand) -> ProveDeliveryResult:
        story = self._stories.get(command.story)
        claim = story.adopt_for_proof(GatePass.ON_RECORD if self._runs.gate_passed(story.id) else GatePass.MISSING,
                                     command.at)
        holders = tuple(self._runs.holding_checkout(story.id))
        if holders:
            return CheckoutHeld(holders)
        def save() -> typing.Tuple[str, str]:
            self._stories.save(story)
            self._events.publish_and_clear_events(story)
            return self._runs.keep_claim(story.id, claim, command.at), self._runs.keep_pass(story.id)

        claim_kept, kept = self._transactions.in_transaction(save)
        return AdoptedForProof(claim, claim_kept, kept)
