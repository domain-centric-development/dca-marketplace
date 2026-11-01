"""A bounded context as the product's spec holds it (WP-173): what it is for, its domain model as its glossary names
it, and its features with the rules and the criteria that hold — and the open stories that would change them."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import AggregateRoot, Id, Value
from .criterion import Criterion, CriterionKey, FeatureName, RuleText
from .delta import Verdict
from .living_spec import LivingSpec


class ContextName(Id):
    """A bounded context by the name its spec folder takes: `cart`, `checkout`."""

    value: str


class Statement(Value):
    """A sentence a person wrote: what a context is for, what a term means, what a story is called."""

    value: str


class Subdomain(Value):
    """How the designed domain classifies a context: Core, Supporting, Generic — as written."""

    value: str


class TermKind(enum.Enum):
    """What a term of a context's glossary is in its domain model, in the order a reader meets them."""

    AGGREGATE = "aggregate"
    ENTITY = "entity"
    VALUE_OBJECT = "value object"
    DOMAIN_EVENT = "domain event"
    DOMAIN_SERVICE = "domain service"
    DOMAIN_GATEWAY = "domain gateway"
    SPECIFICATION = "specification"
    FACTORY = "factory"
    READ_MODEL = "read model"
    FAILURE = "failure"
    CONCEPT = "concept"
    OTHER = "other"

    @staticmethod
    def named(words: Statement) -> typing.Optional[TermKind]:
        """The kind a `**Type:**` line or a section heading names — `Aggregate Root`, `Value Objects`, `Value Object
        (ID)` —, None where it names none (a feature, a note)."""
        said = words.value.lower()
        for kind, marks in KIND_WORDS:
            if any(mark in said for mark in marks):
                return kind
        return None


#: The words that name a kind, the most specific first: "domain event" before "event".
KIND_WORDS: typing.Tuple[typing.Tuple[TermKind, typing.Tuple[str, ...]], ...] = (
    (TermKind.AGGREGATE, ("aggregate",)),
    (TermKind.VALUE_OBJECT, ("value object",)),
    (TermKind.DOMAIN_EVENT, ("domain event", "event")),
    (TermKind.DOMAIN_SERVICE, ("domain service",)),
    (TermKind.DOMAIN_GATEWAY, ("domain gateway", "gateway")),
    (TermKind.SPECIFICATION, ("specification",)),
    (TermKind.FACTORY, ("factor",)),
    (TermKind.READ_MODEL, ("read model",)),
    (TermKind.FAILURE, ("failure", "exception")),
    (TermKind.ENTITY, ("entit",)),
    (TermKind.CONCEPT, ("concept",)),
)


class TermName(Value):
    value: str


class Term(Value):
    """One term of the context's domain model: its name, its kind, what it means."""

    name: TermName
    kind: TermKind
    meaning: Statement


class RuleBlock(Value):
    """A rule of a feature and the criteria that stand under it, in the spec's order; no rule — those before any."""

    rule: typing.Optional[RuleText]
    criteria: typing.Tuple[Criterion, ...]


class Feature(Value):
    """A feature of the context — its folder's name, empty for the context's own file — and what holds in it."""

    name: FeatureName
    criteria: typing.Tuple[Criterion, ...]

    def rules(self) -> typing.Tuple[RuleBlock, ...]:
        """The criteria grouped under their rules, each rule once, in the order the spec first names it."""
        order: typing.List[typing.Optional[RuleText]] = []
        grouped: typing.Dict[typing.Optional[RuleText], typing.List[Criterion]] = {}
        for item in self.criteria:
            if item.rule not in grouped:
                order.append(item.rule)
                grouped[item.rule] = []
            grouped[item.rule].append(item)
        return tuple(RuleBlock(rule, tuple(grouped[rule])) for rule in order)


class StoryRef(Id):
    """An open story by its id."""

    value: str


class OpenStory(Value):
    """A story not delivered yet: its title, its state as written, its context and the criteria it brings."""

    story: StoryRef
    title: Statement
    status: Statement
    context: ContextName
    criteria: typing.Tuple[Criterion, ...]


class PendingChange(Value):
    """What an open story would do to one criterion of the spec: add it, or change it."""

    story: StoryRef
    title: Statement
    status: Statement
    key: CriterionKey
    verdict: Verdict


class ContextSpec(AggregateRoot[ContextName]):
    """A bounded context as the spec holds it: what it is for, its subdomain, its domain model and its features. It
    answers which open stories would change what it holds — never changes it: what holds changes only by a story
    the gate delivers."""

    def __init__(self, name: ContextName, purpose: Statement, subdomain: Subdomain,
                 terms: typing.Sequence[Term], features: typing.Sequence[Feature]) -> None:
        super().__init__()
        self._name = name
        self._purpose = purpose
        self._subdomain = subdomain
        self._terms = tuple(terms)
        self._features = tuple(features)

    @property
    def id(self) -> ContextName:
        return self._name

    @property
    def purpose(self) -> Statement:
        return self._purpose

    @property
    def subdomain(self) -> Subdomain:
        return self._subdomain

    @property
    def features(self) -> typing.Tuple[Feature, ...]:
        return self._features

    def terms_of(self, kind: TermKind) -> typing.Tuple[Term, ...]:
        return tuple(term for term in self._terms if term.kind is kind)

    def held(self) -> typing.Tuple[Criterion, ...]:
        return tuple(item for feature in self._features for item in feature.criteria)

    def pending(self, stories: typing.Sequence[OpenStory]) -> typing.Tuple[PendingChange, ...]:
        """Each criterion an open story of this context adds or changes — one it holds word for word changes
        nothing and is left out; the comparison is the spec's own (`LivingSpec.derived`)."""
        held = self.held()
        found = []
        for story in stories:
            if story.context != self._name:
                continue
            for key, verdict in LivingSpec.derived(story.criteria, held).items():
                if verdict is not Verdict.HOLDS:
                    found.append(PendingChange(story.story, story.title, story.status, key, verdict))
        return tuple(found)
