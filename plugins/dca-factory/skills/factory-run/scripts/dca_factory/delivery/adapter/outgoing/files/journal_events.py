"""The domain's events, published into the journals the factory keeps — a story's event into its story's journal, a
project's own into the factory's — and the boundary a use case writes inside."""

from __future__ import annotations

import dataclasses
import enum
import os
import typing

from .....building_blocks import DomainEvent, DomainEventPublisher, TransactionBoundary
from ....domain.model.delivery_event import DeliveryEvent
from .journal_files import append_event, journal_append, journal_lock
from .request_files import factory_dir

T = typing.TypeVar("T")

#: The kind of a journal line that records a domain event, named by its type.
EVENT_KIND = "event"


def shown(value: typing.Any) -> str:
    """A field of an event as the journal writes it: an enum by its word, a value by its own, a claim by its line, a
    tuple of them joined."""
    if isinstance(value, enum.Enum):
        return str(value.value)
    if isinstance(value, tuple):
        return ",".join(shown(item) for item in value)
    if hasattr(value, "line"):
        return shown(value.line())
    return str(getattr(value, "value", value))


def cells(event: DomainEvent) -> typing.List[str]:
    """The event's fields as `name=value`, its story and its moment left out — the journal line carries them."""
    out = []
    for field in dataclasses.fields(event):  # type: ignore[arg-type]
        if field.name in ("story", "at"):
            continue
        value = getattr(event, field.name)
        if value is not None:
            out.append(f"{field.name}={shown(value)}")
    return out


class JournalEventPublisher(DomainEventPublisher):
    """Each event one line, kind `event`, named by its type: in the journal of the story it names under the run
    folder <runs>, else in the factory's own `events.journal`."""

    def __init__(self, runs: str) -> None:
        self._runs = runs

    def publish(self, event: DomainEvent) -> None:
        if not isinstance(event, DeliveryEvent):
            raise TypeError(f"{type(event).__name__} is no delivery event: it carries no moment `at` and no `story`")
        story, at = event.story, event.at.value
        name = type(event).__name__
        if story is not None:
            journal_append(self._runs, story.value, EVENT_KIND, name, *cells(event), at=at)
        else:
            append_event(os.path.join(factory_dir(), "events.journal"), EVENT_KIND, name, *cells(event), at=at)


class FileTransactions(TransactionBoundary):
    """One writer at a time over the factory's files: a use case's save and its events run under one lock in the
    factory's folder. Files are written in order and nothing is rolled back — a failure between them leaves what was
    written; the lock keeps two writers from interleaving."""

    def in_transaction(self, work: typing.Callable[[], T]) -> T:
        os.makedirs(factory_dir(), exist_ok=True)
        with journal_lock(os.path.join(factory_dir(), "transaction")):
            return work()
