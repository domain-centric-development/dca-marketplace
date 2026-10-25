"""A story: one work order small enough for a single run, and where it stands."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import AggregateRoot, DomainException, Id, Value
from .epic import EpicId


@dataclasses.dataclass(frozen=True)
class StoryId(Id):
    """The name of one story for its whole life: the `id:` of its front matter, else its folder's name."""

    value: str


class StoryStatus(enum.Enum):
    """Where a story stands in its life, as its front matter's `status:` says it."""

    DRAFT = "draft"
    APPROVED = "approved"
    DELIVERED = "delivered"
    SUPERSEDED = "superseded"
    #: no `status:`, or one this release does not know — read as written, never released by the factory
    OTHER = ""


@dataclasses.dataclass(frozen=True)
class Assumption(Value):
    """A line under a story's `## Assumptions`, as written — `- answered: …` where a person settled it."""

    value: str

    def __post_init__(self) -> None:
        if "\n" in self.value or not self.value.strip():
            raise ValueError("an assumption is one line, not empty")


class NotADraft(DomainException):
    """Only a draft is released: an approved, delivered or superseded story runs, or ran, already."""

    def __init__(self, story: StoryId, status: StoryStatus) -> None:
        super().__init__(f"{story.value} is {status.value or 'without a status'} — only a draft is released")


class Story(AggregateRoot[StoryId]):
    """One story: its status, its epic, the assumptions it carries. Released, a draft becomes approved and its
    release an answered assumption."""

    def __init__(self, story_id: StoryId, epic: EpicId, status: StoryStatus,
                 assumptions: typing.Sequence[Assumption] = ()) -> None:
        super().__init__()
        self._id = story_id
        self._epic = epic
        self._status = status
        self._assumptions = list(assumptions)

    @property
    def id(self) -> StoryId:
        return self._id

    @property
    def epic(self) -> EpicId:
        return self._epic

    @property
    def status(self) -> StoryStatus:
        return self._status

    @property
    def assumptions(self) -> typing.Tuple[Assumption, ...]:
        return tuple(self._assumptions)

    def release(self, answered: Assumption) -> None:
        """A person's go: the draft becomes approved, the release kept as the answered assumption."""
        if self._status is not StoryStatus.DRAFT:
            raise NotADraft(self._id, self._status)
        self._status = StoryStatus.APPROVED
        self._assumptions.append(answered)
