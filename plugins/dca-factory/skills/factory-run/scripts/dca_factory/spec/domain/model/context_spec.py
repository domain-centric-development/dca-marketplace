"""A bounded context as the product's spec holds it (WP-173): what it is for, its domain model as its glossary names
it, and its features with the rules and the criteria that hold — and the open stories that would change them. Beside
the contexts, the shared kernel: the model they share, written once (WP-175)."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import AggregateRoot, Id, Value
from .criterion import Criterion, CriterionKey, FeatureName, RuleText, Selector
from .delta import Verdict
from .living_spec import Change


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
    IDENTITY = "identity"
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
        (ID)`, an identity —, None where it names none (a feature, a note)."""
        said = re.sub(r"`[^`]*`", "", words.value).lower()     # a name in code is no kind: `IdentityProvider`
        for kind, marks in KIND_WORDS:
            if any(mark in said for mark in marks):
                return kind
        return None


#: The words that name a kind, the most specific first: "domain event" before "event", an identity — `Value Object (Id)`,
#: `(ID, Shared Kernel)`, `(Identity)` — before the value object it is.
KIND_WORDS: typing.Tuple[typing.Tuple[TermKind, typing.Tuple[str, ...]], ...] = (
    (TermKind.AGGREGATE, ("aggregate",)),
    (TermKind.IDENTITY, ("(identity", "(id)", "(id,")),
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

    def bare(self) -> TermName:
        """The name without what a heading adds in brackets: `Money (borrowed from the Shared Kernel)` is Money."""
        return TermName(re.sub(r"\s*\(.*\)\s*$", "", self.value).strip() or self.value)


class Term(Value):
    """One term of the context's domain model: its name, its kind, what it means."""

    name: TermName
    kind: TermKind
    meaning: Statement


class Origin(enum.Enum):
    """Where a term of a context's model is defined: in its own glossary, or in the shared kernel's."""

    OWN = "own"
    SHARED = "shared"


class ModelTerm(Value):
    """A term as a context's model shows it: one of its own, or one of the shared kernel it uses."""

    term: Term
    origin: Origin


class SharedKernel(Value):
    """The model every context shares, the same in each, as its own glossary names it — no context: no subdomain, no
    features, no criteria."""

    terms: typing.Tuple[Term, ...]

    def defined(self) -> typing.Dict[TermName, Term]:
        return {term.name.bare(): term for term in self.terms}

    def users(self, term: Term, contexts: typing.Sequence[ContextSpec]) -> typing.Tuple[ContextName, ...]:
        """The contexts whose glossary names the term."""
        return tuple(spec.id for spec in contexts if spec.names(term.name.bare()))


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


class Delivery(Value):
    """A delivered story: the criteria it brought, and how it was delivered — `gate`, `hand:<who>`, `adopt`."""

    story: StoryRef
    title: Statement
    context: ContextName
    at: Statement
    how: Statement
    keys: typing.Tuple[CriterionKey, ...]


class Proof(enum.Enum):
    """What stands behind a criterion: a test the code holds, a test it named that the code no longer holds, none."""

    TESTED = "tested"
    ORPHANED = "orphaned"
    UNTESTED = "untested"


class Health(Value):
    """A criterion's standing over the whole spec: what proves it, which named test is gone, who delivered it."""

    key: CriterionKey
    proof: Proof
    missing: typing.Tuple[Selector, ...]
    delivered_by: typing.Optional[Delivery]


class ContextSpec(AggregateRoot[ContextName]):
    """A bounded context as the spec holds it: what it is for, its subdomain, its domain model and its features. It
    answers which open stories would change what it holds — never changes it: what holds changes only by a story
    the gate delivers."""

    def __init__(self, name: ContextName, purpose: Statement, subdomain: Subdomain,
                 terms: typing.Sequence[Term], features: typing.Sequence[Feature],
                 identities: typing.Sequence[TermName] = (), mentions: typing.AbstractSet[TermName] = frozenset()) -> None:
        super().__init__()
        self._name = name
        self._purpose = purpose
        self._subdomain = subdomain
        self._terms = tuple(terms)
        self._features = tuple(features)
        self._identities = tuple(identities)
        self._mentions = frozenset(mentions)

    @classmethod
    def restore(cls, name: ContextName, purpose: Statement, subdomain: Subdomain,
                terms: typing.Sequence[Term], features: typing.Sequence[Feature],
                identities: typing.Sequence[TermName] = (), mentions: typing.AbstractSet[TermName] = frozenset()) -> ContextSpec:
        """The context spec as it was kept — the one way a repository builds it."""
        return cls(name, purpose, subdomain, terms, features, identities, mentions)

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

    def names(self, name: TermName) -> bool:
        """Whether its glossary names the term — as an entry, on an identity line or in code."""
        return name in self._mentions or any(term.name.bare() == name for term in self._terms)

    def model(self, kernel: typing.Optional[SharedKernel]) -> typing.Tuple[ModelTerm, ...]:
        """Its terms, each marked shared where the shared kernel defines it, then each id an identity line names that
        it has no entry for — the shared kernel's where it defines it, else an id of its own without a meaning."""
        shared = kernel.defined() if kernel else {}
        own = tuple(ModelTerm(term, Origin.SHARED if term.name.bare() in shared else Origin.OWN) for term in self._terms)
        named = {term.name.bare() for term in self._terms}
        ids = tuple(ModelTerm(shared[name], Origin.SHARED) if name in shared
                    else ModelTerm(Term(name, TermKind.IDENTITY, Statement("")), Origin.OWN)
                    for name in dict.fromkeys(self._identities) if name not in named)
        return own + ids

    def held(self) -> typing.Tuple[Criterion, ...]:
        return tuple(item for feature in self._features for item in feature.criteria)

    def pending(self, stories: typing.Sequence[OpenStory]) -> typing.Tuple[PendingChange, ...]:
        """Each criterion an open story of this context adds or changes — one it holds word for word changes
        nothing and is left out; the comparison is the spec's own (`Change.derived`)."""
        held = self.held()
        found = []
        for story in stories:
            if story.context != self._name:
                continue
            for key, verdict in Change(tuple(story.criteria)).derived(held).items():
                if verdict is not Verdict.HOLDS:
                    found.append(PendingChange(story.story, story.title, story.status, key, verdict))
        return tuple(found)

    def health(self, located: typing.AbstractSet[Selector],
               deliveries: typing.Sequence[Delivery]) -> typing.Tuple[Health, ...]:
        """Each criterion it holds with what proves it — every named test found, one gone, none named — and the last
        delivered story of this context that brought it (none: adopted or written before the factory)."""
        mine = sorted((d for d in deliveries if d.context == self._name), key=lambda d: d.at.value)
        found = []
        for item in self.held():
            missing = tuple(t for t in item.tests if t not in located)
            proof = Proof.UNTESTED if not item.tests else Proof.ORPHANED if missing else Proof.TESTED
            by = next((d for d in reversed(mine) if item.key in d.keys), None)
            found.append(Health(item.key, proof, missing, by))
        return tuple(found)
