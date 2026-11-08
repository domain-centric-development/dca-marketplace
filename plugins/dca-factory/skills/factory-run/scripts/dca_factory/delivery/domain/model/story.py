"""A story: one work order small enough for a single run, and where it stands."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import AggregateRoot, DomainException, Id, Value
from .epic import EpicId
from .moment import Moment
from .person import Person
from .stage import StoryKind
from .story_words import Count, ContextName, Detail, EventName, RowId, ScenarioClauses, ScenarioKey, StatusWord


class StoryId(Id):
    """The name of one story for its whole life: the `id:` of its front matter, else its folder's name."""

    value: str


class StoryStatus(enum.Enum):
    """Where a story stands in its life, as its front matter's `status:` says it."""

    DRAFT = "draft"
    APPROVED = "approved"
    DELIVERED = "delivered"
    SUPERSEDED = "superseded"
    #: the code exists — the adopt path checks it and builds nothing
    ADOPTED = "adopted"
    #: no `status:`, or one this release does not know — read as written, never released by the factory
    OTHER = ""


class ReleaseState(enum.Enum):
    """Whether a person released the story to be built, as its `status:` says it."""

    #: no `status:` at all — the project may not use the field; nothing to release
    UNMARKED = "unmarked"
    RELEASED = "released"
    #: behaviour the project already has: adopted, never built
    ADOPTED = "adopted"
    DELIVERED = "delivered"
    #: a draft, superseded, or a word nobody knows — a person releases it first
    UNRELEASED = "unreleased"


class KindWord(Value):
    """A story's `kind:` as written — `journey`, `task`, or nothing."""

    value: str

    def kind(self, status: StoryStatus) -> StoryKind:
        """What the story is: a `journey` — a guard over an epic's delivered stories —, a `task` — a change no actor
        sees —, an adoption where its status is `adopted` — behaviour the project already has —, else a story."""
        named = self.value.strip().lower()
        if named == StoryKind.JOURNEY.value:
            return StoryKind.JOURNEY
        if named == StoryKind.TASK.value:
            return StoryKind.TASK
        return StoryKind.ADOPT if status is StoryStatus.ADOPTED else StoryKind.STORY


class Assumption(Value):
    """A line under a story's `## Assumptions`, as written — `- answered: …` where a person settled it."""

    value: str

    def __post_init__(self) -> None:
        if "\n" in self.value or not self.value.strip():
            raise ValueError("an assumption is one line, not empty")


class DeliveredOn(Value):
    """When a story was delivered, as its `delivered:` line says it — "" where the line is missing."""

    value: str


class DeliveredBy(Value):
    """Who claims a delivery: `gate`, `hand:<who>`, or "" for one delivered before the line existed."""

    value: str

    @classmethod
    def hand(cls, person: Person) -> DeliveredBy:
        return cls(f"hand:{person.value}")


#: The gate that delivered a story after its stages.
BY_GATE = DeliveredBy("gate")


class GatePass(enum.Enum):
    """Whether the pass of the gate that delivered a story is on record."""

    ON_RECORD = "on record"
    MISSING = "missing"


class Delivery(Value):
    """A story's delivered lines: when and by whom."""

    on: DeliveredOn
    by: DeliveredBy


class NotADraft(DomainException):
    """Only a draft is released: an approved, delivered or superseded story runs, or ran, already."""

    def __init__(self, story: StoryId, status: StoryStatus) -> None:
        super().__init__(f"{story.value} is {status.value or 'without a status'} — only a draft is released")


class NotDelivered(DomainException):
    """Only a delivered story is taken back or proven: an open story runs as it is."""

    def __init__(self, story: StoryId) -> None:
        super().__init__(f"{story.value} is not delivered")
        self.story = story


class AlreadyDelivered(DomainException):
    """A delivered story is not delivered a second time: a change of delivered behaviour is a new story."""

    def __init__(self, story: StoryId, by: DeliveredBy) -> None:
        super().__init__(f"{story.value} is delivered already ({by.value or 'before delivered_by'})")
        self.story = story
        self.by = by


class NothingToDeliver(DomainException):
    """A superseded story is delivered by none: another story took its place."""

    def __init__(self, story: StoryId) -> None:
        super().__init__(f"{story.value} is superseded — nothing to deliver")
        self.story = story


class NothingToProve(DomainException):
    """A story the gate delivered, its pass on record, is proven already."""

    def __init__(self, story: StoryId) -> None:
        super().__init__(f"{story.value} is delivered by the gate with its pass on record")
        self.story = story


class StoryContent(Value):
    """What a story says, read-only: its context, its criteria and what each observes, the happy paths, what it
    depends on, closes and publishes, the feature it changes, the status as written — the part of the aggregate the
    gate reads, never writes."""

    context: ContextName
    #: its `status:` as written — "" where it has none; the aggregate's `status` is what the factory knows of it
    written_status: StatusWord
    criteria: typing.Tuple[ScenarioKey, ...]
    happy_paths: typing.Tuple[ScenarioKey, ...]
    depends_on: typing.Tuple[StoryId, ...]
    closes: typing.Tuple[RowId, ...]
    publishes: typing.Tuple[EventName, ...]
    #: what each scenario says is observed: its `Then` and every `And` or `But` after it
    clauses: typing.Tuple[ScenarioClauses, ...] = ()
    #: the lines of its `## Changed expectations` a person wrote
    changed_expectations: Count = Count(0)
    #: the feature of its context it changes, as its `feature:` names it — "" where it names none
    feature: Detail = Detail("")


class Story(AggregateRoot[StoryId]):
    """One story: its status, its epic, the assumptions it carries, its delivery, and what it says (`content`: its
    criteria, what it depends on and publishes — read-only, what the gate checks). Released, a draft becomes approved
    and its release an answered assumption. Delivered, it is taken back for a correction, handed to the adopt path to
    prove a claimed delivery, or — built by a person — delivered by hand."""

    def __init__(self, story_id: StoryId, epic: EpicId, status: StoryStatus,
                 assumptions: typing.Sequence[Assumption] = (), delivery: typing.Optional[Delivery] = None,
                 named_kind: KindWord = KindWord(""), *, content: StoryContent) -> None:
        super().__init__()
        self._content = content
        self._named_kind = named_kind
        self._id = story_id
        self._epic = epic
        self._status = status
        self._assumptions = list(assumptions)
        self._delivery = delivery

    @classmethod
    def restore(cls, story_id: StoryId, epic: EpicId, status: StoryStatus,
                assumptions: typing.Sequence[Assumption] = (), delivery: typing.Optional[Delivery] = None,
                named_kind: KindWord = KindWord(""), *, content: StoryContent) -> Story:
        """The story as it was kept — the one way a repository builds it."""
        return cls(story_id, epic, status, assumptions, delivery, named_kind, content=content)

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
    def delivery(self) -> typing.Optional[Delivery]:
        return self._delivery

    @property
    def kind(self) -> StoryKind:
        return self._named_kind.kind(self._status)

    @property
    def assumptions(self) -> typing.Tuple[Assumption, ...]:
        return tuple(self._assumptions)

    def release_state(self) -> ReleaseState:
        """Whether a person released the story: no `status:` is unmarked, `approved` released, `adopted` and
        `delivered` are what they say, any other word is not released."""
        if not self._content.written_status.value:
            return ReleaseState.UNMARKED
        return {StoryStatus.APPROVED: ReleaseState.RELEASED, StoryStatus.ADOPTED: ReleaseState.ADOPTED,
                StoryStatus.DELIVERED: ReleaseState.DELIVERED}.get(self._status, ReleaseState.UNRELEASED)

    def happy_path(self) -> typing.Optional[ScenarioKey]:
        """The one scenario that shows the story's value — None unless exactly one is marked."""
        marked = self._content.happy_paths
        return marked[0] if len(marked) == 1 else None

    def walks(self) -> typing.Tuple[StoryId, ...]:
        """The stories a journey walks — its `depends_on:`; none for any other kind."""
        return self._content.depends_on if self.kind is StoryKind.JOURNEY else ()

    @property
    def content(self) -> StoryContent:
        """What the story says — its criteria, context, dependencies; never changed by the aggregate."""
        return self._content

    def release(self, answered: Assumption) -> None:
        """A person's go: the draft becomes approved, the release kept as the answered assumption."""
        if self._status is not StoryStatus.DRAFT:
            raise NotADraft(self._id, self._status)
        self._status = StoryStatus.APPROVED
        self._assumptions.append(answered)

    def reopen(self) -> None:
        """Taken back for a correction: approved again, it runs from plan, and no longer says delivered."""
        if self._status is not StoryStatus.DELIVERED:
            raise NotDelivered(self._id)
        self._status = StoryStatus.APPROVED
        self._delivery = None

    def adopt_for_proof(self, gate_pass: GatePass) -> Delivery:
        """A claimed delivery handed to the adopt path: adopted, without its delivered lines — the claim they made is
        returned, to be kept. A delivery by the gate whose pass is on record has nothing to prove."""
        if self._status is not StoryStatus.DELIVERED:
            raise NotDelivered(self._id)
        claim = self._delivery or Delivery(DeliveredOn(""), DeliveredBy(""))
        if claim.by == BY_GATE and gate_pass is GatePass.ON_RECORD:
            raise NothingToProve(self._id)
        self._status = StoryStatus.ADOPTED
        self._delivery = None
        return claim

    def deliver_by_hand(self, by: Person, at: Moment) -> Delivery:
        """A person built it: delivered, claimed by them — not proven. Returns the delivery."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else DeliveredBy(""))
        if self._status is StoryStatus.SUPERSEDED:
            raise NothingToDeliver(self._id)
        self._status = StoryStatus.DELIVERED
        self._delivery = Delivery(DeliveredOn(at.value), DeliveredBy.hand(by))
        return self._delivery

    def deliver_by_gate(self, at: Moment) -> Delivery:
        """The gate that delivers it: built or adopted, one end state — delivered, by the gate. Returns the
        delivery."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else DeliveredBy(""))
        self._status = StoryStatus.DELIVERED
        self._delivery = Delivery(DeliveredOn(at.value), BY_GATE)
        return self._delivery
