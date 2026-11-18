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
from .words import Count, Detail, StoryId


class Target(Value):
    """What had to change to correct a finding — a target of delivery's finding class, as its api publishes it."""

    value: str


class LessonKind(enum.Enum):
    """What repeats: the signal a candidate is drawn from."""

    QUESTION = "question"
    FINDING = "finding"
    CORRECTION = "correction"
    ASSUMPTION = "assumption"
    TERM = "term"
    REFUSAL = "refusal"


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
    LessonKind.ASSUMPTION: (LessonPlace.DESCRIPTION, LessonPlace.FACTORY),
    LessonKind.TERM: (LessonPlace.GLOSSARY, LessonPlace.DESCRIPTION, LessonPlace.KNOWLEDGE_CATALOG),
    LessonKind.REFUSAL: (LessonPlace.FACTORY, LessonPlace.PROFILE_CHECK, LessonPlace.INSTRUCTIONS),
}

#: Where a finding's correction goes first, by what had to change (its class's target, WP-221): the recommendation,
#: never the answer.
TARGET_PLACES: typing.Mapping[Target, LessonPlace] = {
    Target("story"): LessonPlace.CRITERION,
    Target("plan"): LessonPlace.DESCRIPTION,
    Target("code"): LessonPlace.PROJECT_RULE,
    Target("test"): LessonPlace.INSTRUCTIONS,
    Target("docs"): LessonPlace.DESCRIPTION,
    Target("glossary"): LessonPlace.GLOSSARY,
    Target("profile"): LessonPlace.PROFILE_CHECK,
}


def places_of(kind: LessonKind, key: SignalKey) -> typing.Tuple[LessonPlace, ...]:
    """The places a candidate offers, the recommended one first; `not-now` and `never` close every list. A question
    about the pipeline goes to the factory alone. A finding counted by its class offers the place its class names,
    the rule suite where a rule could check its type, and the factory."""
    places = PLACES[kind]
    if kind is LessonKind.QUESTION and key.value.endswith("/" + PIPELINE_TAG):
        places = (LessonPlace.FACTORY,)
    target = key.target() if kind is LessonKind.FINDING else None
    if target is not None:
        checkable = key.finding_type() in CHECKABLE
        places = (class_place(target, key.finding_type()),) + ((LessonPlace.RULE_LIBRARY,) if checkable else ()) \
            + (LessonPlace.FACTORY,)
    return places + (LessonPlace.NOT_NOW, LessonPlace.NEVER)


def class_place(target: Target, kind: Detail) -> LessonPlace:
    """The place a finding's class names: a word that drifts the glossary, code a rule only where a rule could
    check its type, else the line that tells the build stage first; every other target its own place."""
    if kind == Detail("domain-term"):
        return LessonPlace.GLOSSARY
    if target == Target("code"):
        return LessonPlace.PROJECT_RULE if kind in CHECKABLE else LessonPlace.INSTRUCTIONS
    return TARGET_PLACES[target]

#: The tag of a question about the pipeline — the factory's to correct, never the project's.
PIPELINE_TAG = "pipeline"

#: The finding types a rule could check from the code alone — the rest a rule cannot see.
CHECKABLE = frozenset({Detail("dead-code"), Detail("relationship"), Detail("domain-boundary")})

#: How many stories a signal repeats in before it is a candidate — counts, written here and nowhere else. A question
#: or a finding is a pattern from its third story on; a correction, an answer to the same assumption and a flagged
#: term from their second.
THRESHOLDS: typing.Mapping[LessonKind, Count] = {
    LessonKind.QUESTION: Count(3),
    LessonKind.FINDING: Count(3),
    LessonKind.CORRECTION: Count(2),
    LessonKind.ASSUMPTION: Count(2),
    LessonKind.TERM: Count(2),
    LessonKind.REFUSAL: Count(3),
}

#: How many stories a placed lesson's signal may come back in before it is asked again, and how many lesson records
#: stand open at a time — the profile's `lessons.backAfter` and `lessons.open` where it names them.
BACK_AFTER = Count(3)
OPEN_AT_ONCE = Count(5)


class SignalKey(Value):
    """What makes two signals the same, as the factory counts them: `<context>/<tag>` for a question,
    `<perspective>/<rule or term>` for a finding, the reason code for a correction, the assumption and its answer,
    the term — lower case."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", " ".join(self.value.lower().split()))

    def target(self) -> typing.Optional[Target]:
        """The target a finding's class key names — `<perspective>/<target>/<type>/<qualifier>` or `<target>/<type>`
        —, None for a key that names none."""
        parts = self.value.split("/")
        word = parts[1] if len(parts) == 4 else (parts[0] if len(parts) == 2 else "")
        return Target(word) if Target(word) in TARGET_PLACES else None

    def finding_type(self) -> Detail:
        """The type a finding's class key names, empty for a key that names none."""
        parts = self.value.split("/")
        return Detail(parts[2] if len(parts) == 4 else (parts[1] if len(parts) == 2 else ""))


class Evidence(Value):
    """Where a signal was seen: the story, and the record, finding row or line that carries it."""

    story: StoryId
    source: Detail


class Signal(Value):
    """One counted occurrence of a kind of deviation; a finding counted on several levels names the coarser key its
    key belongs to (`within`), so a candidate is drawn at the finest level that repeats."""

    kind: LessonKind
    key: SignalKey
    evidence: Evidence
    within: typing.Optional[SignalKey] = None
    #: the words as written, where the key lowered them — an answered assumption's sentence
    said: typing.Optional[Detail] = None
    #: the file of the project description the asking question's tag points to, where one does
    file: typing.Optional[Detail] = None


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
    #: the lesson it was placed as before — drawn again because its signal came back after the answer
    placed: typing.Optional[Decided] = None
    #: a story of the same target without this finding — what right looks like, chosen by order, never by likeness
    contrast: typing.Optional[StoryId] = None
    #: the words a place would keep, as first written — an answered assumption's sentence
    said: typing.Optional[Detail] = None
    #: the file of the project description they would go to, where the questions named one
    file: typing.Optional[Detail] = None

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
    #: the record it was asked in
    record: typing.Optional[Detail] = None

    def lets_back(self, stories: Count, back_after: Count = BACK_AFTER) -> bool:
        """A `not now` lets its candidate come back on more evidence than it was answered on; a place, once its signal
        came back in <back_after> stories more — the place did not hold it; `never` and an open record never."""
        if self.place is LessonPlace.NOT_NOW:
            return stories.value > self.stories.value
        if self.place is None or self.place is LessonPlace.NEVER:
            return False
        return stories.value >= self.stories.value + back_after.value

    @property
    def placed(self) -> bool:
        """Answered with a place — neither waiting, nor `not now`, nor `never`."""
        return self.place not in (None, LessonPlace.NOT_NOW, LessonPlace.NEVER)


class Signals(Value):
    """The signals counted across the stories — what a candidate is drawn from."""

    items: typing.Tuple[Signal, ...]

    def candidates(self, decided: typing.Iterable[Decided],
                   back_after: Count = BACK_AFTER) -> typing.Tuple[Candidate, ...]:
        """A signal that repeats in as many stories as its kind's threshold is one candidate, with the evidence it was
        drawn from — one item per story, the first seen. Below the threshold nothing is drawn. A finding counted on
        several levels is drawn at the finest that repeats: a coarser key only where no key within it was drawn. A
        candidate already asked is not drawn again while its record waits; `never` stops it for good; `not now` lets
        it back once its evidence holds more stories than when it was asked; a placed one once its signal came back
        in <back_after> stories more. An answered assumption copied from one decision into several stories is one
        answer: it counts its different sources, not its stories."""
        grouped: typing.Dict[typing.Tuple[LessonKind, SignalKey], typing.List[Evidence]] = {}
        within: typing.Dict[typing.Tuple[LessonKind, SignalKey], SignalKey] = {}
        for signal in self.items:
            found = grouped.setdefault((signal.kind, signal.key), [])
            if all(e.story != signal.evidence.story for e in found):
                found.append(signal.evidence)
            if signal.within is not None:
                within[(signal.kind, signal.key)] = signal.within
        repeating = {k for k, evidence in grouped.items() if self._weight(k[0], evidence).value >= THRESHOLDS[k[0]].value}
        covered: typing.Set[typing.Tuple[LessonKind, SignalKey]] = set()
        for kind, key in repeating:
            parent = within.get((kind, key))
            while parent is not None:
                covered.add((kind, parent))
                parent = within.get((kind, parent))
        last = {(d.kind, d.key): d for d in decided}
        drawn = []
        for (kind, key), evidence in grouped.items():
            if (kind, key) not in repeating or (kind, key) in covered:
                continue
            before = last.get((kind, key))
            if before is not None and not before.lets_back(Count(len(evidence)), back_after):
                continue
            first = [s for s in self.items if s.kind is kind and s.key == key]
            drawn.append(Candidate(kind, key, tuple(evidence), places_of(kind, key),
                                   before if before is not None and before.placed else None,
                                   self.contrast(kind, key),
                                   next((s.said for s in first if s.said is not None), None),
                                   next((s.file for s in first if s.file is not None), None)))
        return tuple(sorted(drawn, key=lambda c: (c.kind.value, c.key.value)))

    @staticmethod
    def _weight(kind: LessonKind, evidence: typing.Sequence[Evidence]) -> Count:
        """How often a pattern repeats: its stories; an assumption its different sources."""
        return Count(len({e.source for e in evidence}) if kind is LessonKind.ASSUMPTION else len(evidence))

    def stale(self, decided: typing.Sequence[Decided]) -> typing.Tuple[Decided, ...]:
        """The lessons still waiting whose candidate the signals no longer draw — counted wrongly before, or no longer
        repeating: withdrawn, never answered for the person."""
        holding = {(c.kind, c.key) for c in self.candidates([d for d in decided if d.place is not None])}
        return tuple(d for d in decided if d.place is None and (d.kind, d.key) not in holding)

    def contrast(self, kind: LessonKind, key: SignalKey) -> typing.Optional[StoryId]:
        """For a finding counted by its class: the last story that had a finding of the same target and none under
        this key — what right looks like for that target. None for any other key."""
        target = key.target() if kind is LessonKind.FINDING else None
        if target is None:
            return None
        with_key = {s.evidence.story for s in self.items if s.kind is kind and s.key == key}
        same_target = [s.evidence.story for s in self.items
                       if s.kind is kind and s.key.target() == target and s.evidence.story not in with_key]
        return same_target[-1] if same_target else None

    def bounded(self, candidates: typing.Sequence[Candidate], open_now: Count,
                at_once: Count = OPEN_AT_ONCE) -> typing.Tuple[Candidate, ...]:
        """The candidates written now when <open_now> lesson records wait already: at most <at_once> open at a time,
        the most stories first; the rest wait, counted, and come in as one is answered."""
        room = max(0, at_once.value - open_now.value)
        ranked = sorted(candidates, key=lambda c: (-c.stories.value, c.kind.value, c.key.value))
        return tuple(ranked[:room])

    def count(self, kind: LessonKind) -> Count:
        return Count(sum(1 for s in self.items if s.kind is kind))
