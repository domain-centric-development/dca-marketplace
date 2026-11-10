"""A lesson: a deviation that keeps coming back, proposed as a place for its correction, decided by a person.

The loop is the team's. A signal the factory already counts — a question a stage asked, a finding the judge
confirmed, a correction at acceptance, an assumption answered, a term flagged — repeats across stories; counted, at a
threshold, it becomes a candidate with its evidence. A person decides where the correction goes; the skill that owns
the place writes it. Counted, never guessed: no model assigns a kind, a key or a place."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Id, Value
from .story import StoryId
from .story_words import Count, Detail


class LessonKind(enum.Enum):
    """What repeats: the signal a candidate is drawn from."""

    QUESTION = "question"
    FINDING = "finding"
    CORRECTION = "correction"
    ASSUMPTION = "assumption"
    TERM = "term"


class Owner(enum.Enum):
    """Who writes a place: the factory writes none itself. `describe` — the project description's skill; `glossary`
    — the glossary's; `method` — the method's skills, for a project rule or a node of the project's own; `setup` —
    the factory's setup, for a check the profile names; `backlog` — the backlog's skill, for a criterion; `maintainers`
    — nobody here: an issue text for the people who maintain the factory, the rule suite or the knowledge, sent by a
    person; `nobody` — an answer that writes nothing."""

    DESCRIBE = "describe"
    GLOSSARY = "glossary"
    METHOD = "method"
    SETUP = "setup"
    BACKLOG = "backlog"
    MAINTAINERS = "maintainers"
    NOBODY = "nobody"


class LessonPlace(enum.Enum):
    """Where a lesson's correction can go — one option of a lesson record, its first word."""

    DESCRIPTION = "description"
    INSTRUCTIONS = "instructions"
    KNOWLEDGE_NODE = "knowledge-node"
    PROJECT_RULE = "project-rule"
    PROFILE_CHECK = "profile-check"
    CRITERION = "criterion"
    GLOSSARY = "glossary"
    FACTORY = "factory"
    RULE_LIBRARY = "rule-library"
    KNOWLEDGE_CATALOG = "knowledge-catalog"
    NOT_NOW = "not-now"
    NEVER = "never"

    @property
    def owner(self) -> Owner:
        return OWNERS[self]

    @property
    def goes_up(self) -> bool:
        """The correction is the maintainers': the answer writes an anonymised issue text, nothing in the project."""
        return OWNERS[self] is Owner.MAINTAINERS

    @property
    def says(self) -> Detail:
        """The option's words after its place."""
        return SAYS[self]

    @classmethod
    def named(cls, line: Detail) -> typing.Optional[LessonPlace]:
        """The place an option's line opens with — `description — …`, `` `never` — … `` —, None for none."""
        match = re.match(r"^[`*\s]*([a-z-]+)", line.value.strip().lower())
        return next((place for place in cls if match and place.value == match.group(1)), None)


OWNERS: typing.Mapping[LessonPlace, Owner] = {
    LessonPlace.DESCRIPTION: Owner.DESCRIBE,
    LessonPlace.INSTRUCTIONS: Owner.DESCRIBE,
    LessonPlace.KNOWLEDGE_NODE: Owner.METHOD,
    LessonPlace.PROJECT_RULE: Owner.METHOD,
    LessonPlace.PROFILE_CHECK: Owner.SETUP,
    LessonPlace.CRITERION: Owner.BACKLOG,
    LessonPlace.GLOSSARY: Owner.GLOSSARY,
    LessonPlace.FACTORY: Owner.MAINTAINERS,
    LessonPlace.RULE_LIBRARY: Owner.MAINTAINERS,
    LessonPlace.KNOWLEDGE_CATALOG: Owner.MAINTAINERS,
    LessonPlace.NOT_NOW: Owner.NOBODY,
    LessonPlace.NEVER: Owner.NOBODY,
}

SAYS: typing.Mapping[LessonPlace, Detail] = {
    LessonPlace.DESCRIPTION: Detail("a statement of the project description, so the stages read it before they ask"),
    LessonPlace.INSTRUCTIONS: Detail("a line of the project's agent instructions"),
    LessonPlace.KNOWLEDGE_NODE: Detail("a knowledge node of the project's own"),
    LessonPlace.PROJECT_RULE: Detail("an architecture rule of the project's own, so the suite catches it"),
    LessonPlace.PROFILE_CHECK: Detail("a check the profile names, run at the gate"),
    LessonPlace.CRITERION: Detail("a criterion or a test the stories of this kind lack"),
    LessonPlace.GLOSSARY: Detail("an entry of the glossary, so the gate looks for the word"),
    LessonPlace.FACTORY: Detail("the factory itself got this wrong — an issue text for its maintainers"),
    LessonPlace.RULE_LIBRARY: Detail("the method's rule suite could catch this — an issue text for its maintainers"),
    LessonPlace.KNOWLEDGE_CATALOG: Detail("the method's knowledge should have said this — an issue text for its "
                                          "maintainers"),
    LessonPlace.NOT_NOW: Detail("asked again once the evidence has grown"),
    LessonPlace.NEVER: Detail("the same candidate does not come back"),
}

#: The places a candidate offers by kind, the recommended one first; `not-now` and `never` close every list.
PLACES: typing.Mapping[LessonKind, typing.Tuple[LessonPlace, ...]] = {
    LessonKind.QUESTION: (LessonPlace.DESCRIPTION, LessonPlace.INSTRUCTIONS, LessonPlace.KNOWLEDGE_NODE,
                          LessonPlace.KNOWLEDGE_CATALOG, LessonPlace.FACTORY),
    LessonKind.FINDING: (LessonPlace.PROJECT_RULE, LessonPlace.PROFILE_CHECK, LessonPlace.KNOWLEDGE_NODE,
                         LessonPlace.RULE_LIBRARY, LessonPlace.FACTORY),
    LessonKind.CORRECTION: (LessonPlace.DESCRIPTION, LessonPlace.CRITERION, LessonPlace.FACTORY),
    LessonKind.ASSUMPTION: (LessonPlace.DESCRIPTION, LessonPlace.INSTRUCTIONS),
    LessonKind.TERM: (LessonPlace.GLOSSARY, LessonPlace.DESCRIPTION, LessonPlace.KNOWLEDGE_CATALOG),
}

#: How many stories a signal repeats in before it is a candidate — counts, written here and nowhere else. A question
#: or a finding is a pattern from its third story on; a correction, an answer to the same assumption and a flagged
#: term from their second.
THRESHOLDS: typing.Mapping[LessonKind, Count] = {
    LessonKind.QUESTION: Count(3),
    LessonKind.FINDING: Count(3),
    LessonKind.CORRECTION: Count(2),
    LessonKind.ASSUMPTION: Count(2),
    LessonKind.TERM: Count(2),
}


class SignalKey(Value):
    """What makes two signals the same, as the factory counts them: `<context>/<tag>` for a question,
    `<perspective>/<rule or term>` for a finding, the reason code for a correction, the assumption and its answer,
    the term — lower case."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", " ".join(self.value.lower().split()))


class Evidence(Value):
    """Where a signal was seen: the story, and the record, finding row or line that carries it."""

    story: StoryId
    source: Detail


class Signal(Value):
    """One counted occurrence of a kind of deviation."""

    kind: LessonKind
    key: SignalKey
    evidence: Evidence


class LessonId(Id):
    """A lesson's name, from its kind and its key: `lesson-<kind>-<key as a slug>` — the same candidate, the same id."""

    value: str

    @classmethod
    def of(cls, kind: LessonKind, key: SignalKey) -> LessonId:
        slug = re.sub(r"[^a-z0-9]+", "-", key.value).strip("-")[:48].strip("-") or "pattern"
        return cls(f"lesson-{kind.value}-{slug}")


class Candidate(Value):
    """A pattern at its threshold: its kind, its key, the evidence it was drawn from (one per story, in story order),
    and the places it offers, the recommended one first."""

    kind: LessonKind
    key: SignalKey
    evidence: typing.Tuple[Evidence, ...]
    places: typing.Tuple[LessonPlace, ...]

    @property
    def id(self) -> LessonId:
        return LessonId.of(self.kind, self.key)

    @property
    def recommended(self) -> LessonPlace:
        return self.places[0]

    @property
    def stories(self) -> Count:
        return Count(len({e.story for e in self.evidence}))


class Decided(Value):
    """A lesson already asked: which candidate (its kind and key), the place its answer named (None while it waits),
    and how many stories its evidence held when it was asked."""

    kind: LessonKind
    key: SignalKey
    place: typing.Optional[LessonPlace]
    stories: Count

    def lets_back(self, stories: Count) -> bool:
        """Only a `not now` lets its candidate come back, and only on more evidence than it was answered on."""
        return self.place is LessonPlace.NOT_NOW and stories.value > self.stories.value


class Signals(Value):
    """The signals counted across the stories — what a candidate is drawn from."""

    items: typing.Tuple[Signal, ...]

    def candidates(self, decided: typing.Iterable[Decided]) -> typing.Tuple[Candidate, ...]:
        """A signal that repeats in as many stories as its kind's threshold is one candidate, with the evidence it was
        drawn from — one item per story, the first seen. Below the threshold nothing is drawn. A candidate already
        asked is not drawn again while its record waits or after a person placed it; `never` stops it for good; `not
        now` lets it back once its evidence holds more stories than when it was asked."""
        grouped: typing.Dict[typing.Tuple[LessonKind, SignalKey], typing.List[Evidence]] = {}
        for signal in self.items:
            found = grouped.setdefault((signal.kind, signal.key), [])
            if all(e.story != signal.evidence.story for e in found):
                found.append(signal.evidence)
        last = {(d.kind, d.key): d for d in decided}
        drawn = []
        for (kind, key), evidence in grouped.items():
            before = last.get((kind, key))
            if len(evidence) < THRESHOLDS[kind].value or (before is not None
                                                          and not before.lets_back(Count(len(evidence)))):
                continue
            drawn.append(Candidate(kind, key, tuple(evidence), PLACES[kind] + (LessonPlace.NOT_NOW, LessonPlace.NEVER)))
        return tuple(sorted(drawn, key=lambda c: (c.kind.value, c.key.value)))

    def count(self, kind: LessonKind) -> Count:
        return Count(sum(1 for s in self.items if s.kind is kind))
