"""The building blocks — the markers of DCA's tactical patterns and ports, by the names `dca-building-blocks` gives them.

Outside every bounded context, as the building blocks are a dependency of every module and of none of them: the
domain, the application and the adapters of each context import from here, this module imports nothing of theirs.
stdlib only — frozen dataclasses, `typing.Protocol`, `abc`. A subclass of `Value`, `Id` or `DomainEvent` is a frozen
dataclass by its base: it declares its fields and carries no decorator of its own.

    Value, Id                  a characteristic without identity; the identifier of one entity for its whole life
    Entity, AggregateRoot      a domain object known by its identity; the entry to a cluster, collecting its events
    DomainEvent                something that happened in the domain, named in the past tense
    DomainService              a stateless operation of the domain that belongs to no single object
    DomainException            a business rule broken, in the language of the model
    InputPort, UseCase         the entry to the application; one user action or system operation
    OutputPort                 what the application needs from outside, implemented by an outgoing adapter
    Repository, Store          aggregates with a life cycle; operational data recorded or looked up without one
    UseCaseException           a use case's failure about the request, not about an invariant

A marker that exists is not a duty to use it: an entity, an aggregate, a repository is used where something has a
life cycle, a value where something is described.
"""

from __future__ import annotations

import abc
import dataclasses
import typing


def _frozen(cls: type) -> None:
    """Make a subclass of a marker a frozen dataclass — the markers themselves, declared here, stay plain classes."""
    if cls.__module__ != __name__:
        dataclasses.dataclass(frozen=True)(cls)


@typing.dataclass_transform(frozen_default=True)   # the type checker's view of the same
class Value:
    """Marker for Value Objects.

    A value describes a characteristic — an option's key, a moment, a count of tokens — and has no identity: two values
    with the same attributes are the same value. It is immutable; a change produces a new instance. Having no life
    cycle of its own, it is never loaded or saved alone — it travels inside the entity or aggregate that holds it.

    - immutable, with attribute equality: every subclass is a frozen dataclass by this base, without a decorator;
    - self-validating: `__post_init__` rejects what makes no sense in the domain;
    - behaviour without side effects, returning new values;
    - it references no aggregate root and no entity.

        class OptionKey(Value):
            value: str

            def __post_init__(self) -> None:
                if not OPTION_KEY.fullmatch(self.value):
                    raise ValueError(f"{self.value!r} is no option key")

    A primitive of the domain is wrapped in one, a field named `value`; an identifier carries its own marker, `Id`.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        super().__init_subclass__(**kwargs)
        _frozen(cls)


class Id(Value):
    """Marker for typed identifiers of entities and aggregate roots.

    An identifier is a value whose only job is to name one entity for its whole life. One type per entity
    (`StoryId`, `RecordId`) instead of a bare `str` lets the type checker reject one aggregate's id where another's is
    expected, and lets a repository's signature say which aggregate it manages. It validates its wrapped value and
    carries no behaviour beyond identity; it lives in the domain of the context that owns the entity — in the shared
    kernel where several contexts share it.
    """

    __slots__ = ()


ID = typing.TypeVar("ID", bound=Id)
#: An identifier a port only takes — a protocol's type variable that appears in arguments alone.
ID_IN = typing.TypeVar("ID_IN", bound=Id, contravariant=True)


class Entity(abc.ABC, typing.Generic[ID]):
    """Marker for Entities.

    An entity is defined by its identity, not by its attributes: it stays the same while its state changes, and two
    with equal attributes are still two. Every entity carries a typed identifier (`Id`) that is stable for its life.
    An entity that is not itself an aggregate root lives inside exactly one aggregate: created, changed and removed
    only through its root, never loaded or saved alone, never returned from a repository.

    - it has an identifier, `id`;
    - equality means identity: `same_identity_as` compares identifiers only;
    - it changes state through behaviour named in the ubiquitous language, never through setters;
    - it holds no reference to an aggregate root — it is reached from the root, not the other way.
    """

    @property
    @abc.abstractmethod
    def id(self) -> ID:
        """The identifier this entity is known by for its whole life."""

    def same_identity_as(self, other: typing.Optional[Entity[ID]]) -> bool:
        """Whether <other> is the same entity — the same identifier, whatever the attributes; False for None."""
        return other is not None and self.id == other.id


@typing.dataclass_transform(frozen_default=True)   # the type checker's view of the same
class DomainEvent:
    """Marker for Domain Events.

    Something that happened in the domain that domain experts care about, named in the past tense
    (`DeliveryAccepted`, `StoryReleased`). Immutable — a frozen dataclass by this base —, it carries when it happened as a value of
    the domain's own and the event's data; it is data, not a component, and internal to its bounded context, so it
    evolves without versioning. An aggregate registers it during a state change; the use case publishes and clears
    the events once the aggregate is saved.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        super().__init_subclass__(**kwargs)
        _frozen(cls)


class AggregateRoot(Entity[ID]):
    """The entry point to an aggregate — a cluster of domain objects treated as one unit — and its events.

    The root maintains the invariants within the aggregate and collects the domain events its state changes raise.
    The events are published after the aggregate is saved, and then cleared — one step for the use case:

        story.release(assumption)        # 1. the aggregate performs the operation and registers its event
        stories.save(story)              # 2. the repository saves the aggregate
        events.publish_and_clear(story)  # 3. the use case publishes and clears the events

    It holds no reference to a repository or another output port, and no other aggregate root — another aggregate
    is referenced by its id.
    """

    def __init__(self) -> None:
        self._domain_events: typing.List[DomainEvent] = []

    def register_event(self, event: DomainEvent) -> None:
        """Register an event to be published after the aggregate is saved — from the aggregate's own behaviour
        only, when something happened that other parts of the system may care about."""
        if event is None:
            raise ValueError("a domain event cannot be None")
        self._domain_events.append(event)

    def domain_events(self) -> typing.Tuple[DomainEvent, ...]:
        """The events its state changes raised since they were last cleared, in order."""
        return tuple(self._domain_events)

    def clear_domain_events(self) -> None:
        """Clear the events once they are published, so none is published twice."""
        self._domain_events.clear()


class DomainService:
    """Marker for Domain Services.

    A stateless operation of the domain that belongs naturally to no entity or value — logic that involves several
    domain objects or spans aggregates. Named after an activity in the ubiquitous language, it holds nothing but its
    dependencies, knows no container, and is created and called by the application. Its operations take an
    aggregate or an entity.
    """

    __slots__ = ()


class DomainGateway(typing.Protocol):
    """Marker for Domain Gateways — an interface the domain declares to obtain facts it does not hold, in its own
    language, implemented by an outgoing adapter. It never writes to the outside: it enriches the model so the model
    can decide. A domain service or an aggregate calls it where a lookup is needed for some of what it decides on
    only, so the use case does not read every fact up front; the rationale stands beside its declaration."""


class DomainException(Exception):
    """The base of every business rule the domain model reports as broken.

    It has a name a domain expert would recognise: which rule of the model was broken, not which technical operation
    failed. An argument guard is no domain exception — a check of what a caller must never pass stays the platform's
    own (`ValueError`, `TypeError`). It lives in the domain beside the model that raises it and names no transport
    vocabulary; translating it into a protocol's answer is the incoming adapter's work.
    """


class InputPort(typing.Protocol):
    """Marker for Input Ports — the entry points to the application, called by the incoming (driving) adapters: a
    command line, an HTTP handler, a folder watched for requests, a timer, a hook. Technology-agnostic, defined in the
    application's terms, implemented by a use case."""


INPUT = typing.TypeVar("INPUT", contravariant=True)
OUTPUT = typing.TypeVar("OUTPUT", covariant=True)


class UseCase(InputPort, typing.Protocol[INPUT, OUTPUT]):
    """One user action or system operation: it takes a command or a query and returns a result, never an entity.

    The input port is `<Action><Concept>InputPort(UseCase[<Command>, <Result>])` and declares nothing of its own; the
    class implementing it is `<Action><Concept>UseCase`. Where an operation has several outcomes, the result is a
    union of frozen dataclasses (`Accepted | NeedsSkill`), matched at the adapter; a failure stays an exception.
    A use case never calls another use case.
    """

    def execute(self, command: INPUT) -> OUTPUT:
        """Execute this use case with its command or query."""
        ...


class OutputPort(typing.Protocol):
    """Marker for Output Ports — what the application needs from the outside world and does not implement itself:
    the files a project keeps, git, a tool's process, a build command. Declared in the application, in the
    application's terms; implemented by an outgoing (driven) adapter."""


AGGREGATE = typing.TypeVar("AGGREGATE", bound=AggregateRoot[typing.Any])


class Repository(OutputPort, typing.Protocol[AGGREGATE, ID_IN]):
    """A collection-like port for the aggregate roots of one type — one repository per root, never per entity.

    It loads and saves whole aggregates and speaks the domain's language; the interface is an output port in the
    application (`application/shared/`), the implementation an outgoing adapter. `find_by_id`, `save` and
    `delete_by_id` are the deliberate minimum of an aggregate's life cycle; a port adds the questions its use cases
    ask.
    """

    def find_by_id(self, aggregate_id: ID_IN) -> typing.Optional[AGGREGATE]:
        """The aggregate with this id, or None."""
        ...

    def save(self, aggregate: AGGREGATE) -> AGGREGATE:
        """Add or update the aggregate; its events are published by the use case afterwards."""
        ...

    def delete_by_id(self, aggregate_id: ID_IN) -> None:
        """Remove the aggregate from the collection."""
        ...


class Store(OutputPort, typing.Protocol):
    """Marker for Stores — output ports that record or look up operational data without an aggregate life cycle:
    a journal appended to, a queue of requests, usage recorded and counted. A lookup by key is fine on a store; an
    aggregate's life cycle needs a repository. In doubt: where what is stored is a value or a record, it is a store."""


class UseCaseException(Exception):
    """The base of every use-case failure the application reports to its callers.

    A use case fails for reasons the model cannot state on its own, because they are about the request: the addressed
    aggregate does not exist, a precondition on a second aggregate does not hold. One type per outcome, so a caller
    tells them apart without reading a message. A broken rule of the model is a `DomainException`; an argument guard
    stays the platform's own. It names no transport vocabulary — the incoming adapter maps it onto its protocol's
    answer.
    """
