"""A story: one work order small enough for a single run, and where it stands."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import AggregateRoot, DomainEvent, DomainException, Id, Value
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


class Releasing(enum.Enum):
    """What the project asks before a story is delivered: a person's release (`release: required` in its profile),
    or nothing more than that a story is not a draft — a story without `status:` not held back."""

    REQUIRED = "required"
    OPTIONAL = "optional"


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


class NamedKind(enum.Enum):
    """A story's `kind:` as its front matter names it — `journey`, `task`, or none (any other word names none)."""

    JOURNEY = "journey"
    TASK = "task"
    NONE = ""

    def kind(self, status: StoryStatus) -> StoryKind:
        """What the story is: a `journey` — a guard over an epic's delivered stories —, a `task` — a change no actor
        sees —, an adoption where its status is `adopted` — behaviour the project already has —, else a story."""
        if self is NamedKind.JOURNEY:
            return StoryKind.JOURNEY
        if self is NamedKind.TASK:
            return StoryKind.TASK
        return StoryKind.ADOPT if status is StoryStatus.ADOPTED else StoryKind.STORY


class Assumption(Value):
    """A line under a story's `## Assumptions`, as written — `- answered: …` where a person settled it."""

    value: str

    def __post_init__(self) -> None:
        if "\n" in self.value or not self.value.strip():
            raise ValueError("an assumption is one line, not empty")

    @classmethod
    def answered(cls, sentence: Detail, cites: Detail) -> Assumption:
        """An assumption settled: `- answered: <sentence> (<what it cites>)`."""
        return cls(f"- answered: {sentence.value} ({cites.value})")


#: What the plan's own adoption cites in the answered line it leaves: no decision record, the plan's `## Adopt`.
PLAN_ADOPT = Detail("plan-adopt")


class DeliveredOn(Value):
    """When a story was delivered, as its `delivered:` line says it — "" where the line is missing."""

    value: str


class Deliverer(enum.Enum):
    """Who claims a delivery: the gate after the stages, a person by hand, or nobody known — a story delivered before
    the line existed."""

    GATE = "gate"
    HAND = "hand"
    UNKNOWN = "unknown"


class DeliveredBy(Value):
    """Who claims a delivery, and the person where it was a hand delivery."""

    deliverer: Deliverer
    person: typing.Optional[Person] = None

    @classmethod
    def hand(cls, person: Person) -> DeliveredBy:
        return cls(Deliverer.HAND, person)

    def line(self) -> Detail:
        """The claim as the story's `delivered_by:` says it: `gate`, `hand:<who>`, or nothing."""
        if self.deliverer is Deliverer.GATE:
            return Detail(Deliverer.GATE.value)
        if self.deliverer is Deliverer.HAND:
            return Detail(f"{Deliverer.HAND.value}:{self.person.value if self.person else ''}")
        return Detail("")


#: The gate that delivered a story after its stages.
BY_GATE = DeliveredBy(Deliverer.GATE)
#: A delivery whose claimant nobody recorded.
BY_NOBODY_KNOWN = DeliveredBy(Deliverer.UNKNOWN)


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
        super().__init__(f"{story.value} is delivered already ({by.line().value or 'before delivered_by'})")
        self.story = story
        self.by = by


class NothingToDeliver(DomainException):
    """A superseded story is delivered by none: another story took its place."""

    def __init__(self, story: StoryId) -> None:
        super().__init__(f"{story.value} is superseded — nothing to deliver")
        self.story = story


class NotReleased(DomainException):
    """Only a story a person released, or one the project already has, is delivered by the gate: a draft, or a status
    nobody knows, is released first."""

    def __init__(self, story: StoryId, status: StoryStatus) -> None:
        super().__init__(f"{story.value} is {status.value or 'of a status the factory does not know'} — a person "
                         f"releases it (`status: approved`) before the gate delivers it")
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


class StoryReleased(DomainEvent):
    """A person released the draft: it is approved and may be built."""

    story: StoryId
    by: Person
    at: Moment


class CitedCorrection(Value):
    """A correction a person gave on looking at the delivered story, answered in its acceptance record and written
    into the story — what a story is reopened for. The record is named by its id: it is another aggregate."""

    record: Detail


class StoryReopened(DomainEvent):
    """A delivered story was taken back for a correction: approved again, it runs from plan."""

    story: StoryId
    correction: Detail
    at: Moment


class StoryAdoptedForProof(DomainEvent):
    """A claimed delivery was handed to the adopt path, to be proven by the existing tests."""

    story: StoryId
    #: the claim the story was delivered under, replaced by the proof
    claimed_by: DeliveredBy
    at: Moment


class StoryAdoptedOnPlan(DomainEvent):
    """The plan found every scenario of the released story holding on today's code: adopted, it is proven, never
    built."""

    story: StoryId
    at: Moment


class PublicationTakenBack(DomainEvent):
    """A delivery published on the story's branch was taken back — its merge request lost the race —: the story is
    as it was before it was published, to be delivered again."""

    story: StoryId
    at: Moment


class AnswerTaken(DomainEvent):
    """An answer a stage applied became an answered line of the story: the story carries it from now on."""

    story: StoryId
    cites: Detail
    at: Moment


class ScenariosSplitOff(DomainEvent):
    """The plan found some scenarios of the released story holding on today's code: they moved into an adopted story
    of their own, the story builds the rest."""

    story: StoryId
    into: StoryId
    scenarios: typing.Tuple[ScenarioKey, ...]
    at: Moment


class StoryDeliveredByHand(DomainEvent):
    """A person built the story and delivered it — claimed, not proven."""

    story: StoryId
    by: Person
    at: Moment


class StoryDeliveredByGate(DomainEvent):
    """The gate delivered the story: built or adopted, it holds."""

    story: StoryId
    at: Moment


class Story(AggregateRoot[StoryId]):
    """One story: its status, its epic, the assumptions it carries, its delivery, and what it says (`content`: its
    criteria, what it depends on and publishes — read-only, what the gate checks). Released, a draft becomes approved
    and its release an answered assumption. Delivered, it is taken back for a correction, handed to the adopt path to
    prove a claimed delivery, or — built by a person — delivered by hand."""

    def __init__(self, story_id: StoryId, epic: EpicId, status: StoryStatus,
                 assumptions: typing.Sequence[Assumption] = (), delivery: typing.Optional[Delivery] = None,
                 named_kind: NamedKind = NamedKind.NONE, *, content: StoryContent,
                 releasing: Releasing = Releasing.OPTIONAL) -> None:
        super().__init__()
        #: whether the project delivers only what a person released: a draft, or a story without `status:`, never
        self._release_required = releasing is Releasing.REQUIRED
        self._content = content
        #: whether the story carries a `status:` line — a project may not use the field; any transition writes one
        self._marked = bool(content.written_status.value)
        self._named_kind = named_kind
        self._id = story_id
        self._epic = epic
        self._status = status
        self._assumptions = list(assumptions)
        self._delivery = delivery
        #: a story made in this life of the aggregate by a split: where it came from, when
        self._split_from: typing.Optional[StoryId] = None
        self._created: typing.Optional[Moment] = None
        #: the scenarios this story gave away in this life of the aggregate
        self._split_off: typing.Tuple[ScenarioKey, ...] = ()

    @classmethod
    def restore(cls, story_id: StoryId, epic: EpicId, status: StoryStatus,
                assumptions: typing.Sequence[Assumption] = (), delivery: typing.Optional[Delivery] = None,
                named_kind: NamedKind = NamedKind.NONE, *, content: StoryContent,
                releasing: Releasing = Releasing.OPTIONAL) -> Story:
        """The story as it was kept — the one way a repository builds it; <releasing> the project's rule."""
        return cls(story_id, epic, status, assumptions, delivery, named_kind, content=content, releasing=releasing)

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
        if not self._marked:
            # no `status:` at all: a draft where the project requires a release, else not held back
            return ReleaseState.UNRELEASED if self._release_required else ReleaseState.UNMARKED
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
    def split_from(self) -> typing.Optional[StoryId]:
        """The story this one was split from in this life of the aggregate — None for one read as it was kept."""
        return self._split_from

    @property
    def created(self) -> typing.Optional[Moment]:
        """When a story made in this life of the aggregate was made."""
        return self._created

    @property
    def split_off_scenarios(self) -> typing.Tuple[ScenarioKey, ...]:
        """The scenarios this story gave away in this life of the aggregate."""
        return self._split_off

    @property
    def content(self) -> StoryContent:
        """What the story says — its criteria, context, dependencies; never changed by the aggregate."""
        return self._content

    def release(self, by: Person, request: Detail, at: Moment) -> None:
        """A person's go, through the request they made: the draft becomes approved, the release kept as an answered
        assumption naming who, when and the request."""
        if self._status is not StoryStatus.DRAFT and self._marked:
            raise NotADraft(self._id, self._status)
        self._status = StoryStatus.APPROVED
        self._marked = True
        self._assumptions.append(Assumption(f"- answered: the story is released for building (request "
                                            f"{request.value}, {by.value}, {at.value})."))
        self.register_event(StoryReleased(self._id, by, at))

    def reopen(self, correction: CitedCorrection, at: Moment) -> None:
        """Taken back for the correction it cites: approved again, it runs from plan, and no longer says delivered."""
        if self._status is not StoryStatus.DELIVERED:
            raise NotDelivered(self._id)
        self._status = StoryStatus.APPROVED
        self._marked = True
        self._delivery = None
        self.register_event(StoryReopened(self._id, correction.record, at))

    def adopt_for_proof(self, gate_pass: GatePass, at: Moment) -> Delivery:
        """A claimed delivery handed to the adopt path: adopted, without its delivered lines — the claim they made is
        returned, to be kept. A delivery by the gate whose pass is on record has nothing to prove."""
        if self._status is not StoryStatus.DELIVERED:
            raise NotDelivered(self._id)
        claim = self._delivery or Delivery(DeliveredOn(""), BY_NOBODY_KNOWN)
        if claim.by == BY_GATE and gate_pass is GatePass.ON_RECORD:
            raise NothingToProve(self._id)
        self._status = StoryStatus.ADOPTED
        self._marked = True
        self._delivery = None
        self.register_event(StoryAdoptedForProof(self._id, claim.by, at))
        return claim

    def take_answer(self, sentence: Detail, cites: Detail, at: Moment) -> bool:
        """An answer a stage applied, an answered line of the story — once per record it cites: False where the story
        carries it already."""
        if any(f"({cites.value})" in assumption.value for assumption in self._assumptions):
            return False
        self._assumptions.append(Assumption.answered(sentence, cites))
        self.register_event(AnswerTaken(self._id, cites, at))
        return True

    def adopt_on_plan(self, answered: Assumption, at: Moment) -> None:
        """The plan found every scenario holding: the released story is adopted, the plan's finding kept as its
        answered assumption."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else BY_NOBODY_KNOWN)
        if self.release_state() not in (ReleaseState.RELEASED, ReleaseState.UNMARKED):
            raise NotReleased(self._id, self._status)
        self._status = StoryStatus.ADOPTED
        self._marked = True
        if answered not in self._assumptions:
            self._assumptions.append(answered)
        self.register_event(StoryAdoptedOnPlan(self._id, at))

    def take_back_publication(self, published_over: StoryStatus, at: Moment) -> None:
        """A published delivery taken back: the story is again what it was published over — approved, or adopted
        where the adopt path delivered it —, without its delivered lines."""
        if self._status is not StoryStatus.DELIVERED:
            raise NotDelivered(self._id)
        self._status = published_over if published_over is StoryStatus.ADOPTED else StoryStatus.APPROVED
        self._marked = True
        self._delivery = None
        self.register_event(PublicationTakenBack(self._id, at))

    def split_off(self, scenarios: typing.Tuple[ScenarioKey, ...], held: Detail, at: Moment) -> Story:
        """The plan found these scenarios holding, not the whole story: they move into an adopted story of their own,
        `<id>-holds`, in the same epic; this story keeps the rest and says where they went. Returns the new story."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else BY_NOBODY_KNOWN)
        if self.release_state() not in (ReleaseState.RELEASED, ReleaseState.UNMARKED):
            raise NotReleased(self._id, self._status)
        into = StoryId(f"{self._id.value}-holds")
        moved = set(scenarios)
        kept = self._content
        split = Story(into, self._epic, StoryStatus.ADOPTED,
                      [Assumption.answered(Detail(f"split from `{self._id.value}` — {held.value}"), PLAN_ADOPT)],
                      content=dataclasses.replace(
                          kept, written_status=StatusWord(StoryStatus.ADOPTED.value),
                          criteria=tuple(scenarios), happy_paths=(), depends_on=(),
                          closes=(), publishes=(), clauses=tuple(c for c in kept.clauses if c.key in moved),
                          changed_expectations=Count(0)))
        split._split_from = self._id
        split._created = at
        split.register_event(StoryAdoptedOnPlan(into, at))
        self._content = dataclasses.replace(
            kept, criteria=tuple(k for k in kept.criteria if k not in moved),
            happy_paths=tuple(k for k in kept.happy_paths if k not in moved),
            clauses=tuple(c for c in kept.clauses if c.key not in moved))
        self._split_off = tuple(scenarios)
        self._assumptions.append(Assumption.answered(
            Detail(f"{', '.join(k.value for k in scenarios)} hold on today's code, and no delivered story carries "
                   f"them — the plan split them into the adopted story `{into.value}`"), PLAN_ADOPT))
        self.register_event(ScenariosSplitOff(self._id, into, tuple(scenarios), at))
        return split

    def deliver_by_hand(self, by: Person, at: Moment) -> Delivery:
        """A person built it: delivered, claimed by them — not proven. Returns the delivery."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else BY_NOBODY_KNOWN)
        if self._status is StoryStatus.SUPERSEDED:
            raise NothingToDeliver(self._id)
        if self._release_required and self.release_state() is ReleaseState.UNRELEASED:
            raise NotReleased(self._id, self._status)
        self._status = StoryStatus.DELIVERED
        self._marked = True
        self._delivery = Delivery(DeliveredOn(at.value), DeliveredBy.hand(by))
        self.register_event(StoryDeliveredByHand(self._id, by, at))
        return self._delivery

    def deliver_by_gate(self, at: Moment) -> Delivery:
        """The gate that delivers it: built or adopted, one end state — delivered, by the gate. Returns the
        delivery. Only what a person released, or the project already has, is delivered; a story without a `status:`
        is not held back — the project may not use the field."""
        if self._status is StoryStatus.DELIVERED:
            raise AlreadyDelivered(self._id, self._delivery.by if self._delivery else BY_NOBODY_KNOWN)
        if self._status is StoryStatus.SUPERSEDED:
            raise NothingToDeliver(self._id)
        if self.release_state() is ReleaseState.UNRELEASED:
            raise NotReleased(self._id, self._status)
        self._status = StoryStatus.DELIVERED
        self._marked = True
        self._delivery = Delivery(DeliveredOn(at.value), BY_GATE)
        self.register_event(StoryDeliveredByGate(self._id, at))
        return self._delivery
