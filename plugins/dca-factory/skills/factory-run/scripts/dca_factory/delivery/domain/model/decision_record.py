"""A decision record: a question a run may not answer itself, and the person's answer."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import AggregateRoot, DomainEvent, DomainException, Id, Value
from .moment import Moment
from .person import Person
from .stage import StageName
from .story import StoryId
from .story_words import Detail


class RecordId(Id):
    """The name of one decision record: the `id:` of its front matter, else its file's name."""

    value: str


#: An option's key as a record lists it: one to three letters or digits.
KEY = re.compile(r"^[A-Za-z0-9]{1,3}$")


class OptionKey(Value):
    """One option of a record, by its key — `a`, `B`, `1`."""

    value: str

    def __post_init__(self) -> None:
        if not KEY.match(self.value):
            raise ValueError(f"{self.value!r} is no option key")


class OptionLine(Value):
    """An option as the record offers it: its key and its first line."""

    key: OptionKey
    line: Detail


#: An answer that names an option by its label: `a`, `B`, `option b`, `(c)`.
LABEL = re.compile(r"^(?:option\s+)?\(?([A-Za-z0-9]{1,3})[.):*\s]*$", re.I)


class DecisionState(enum.Enum):
    """Where a record stands: no answer, an answer section not yet complete, answered, applied by a stage."""

    OPEN = "open"
    DRAFT = "draft"
    ANSWERED = "answered"
    APPLIED = "applied"

    @classmethod
    def of(cls, sections: typing.AbstractSet[Section], given: typing.AbstractSet[AnswerField]) -> DecisionState:
        """`## Applied` makes a record applied, no `## Answer` leaves it open, an answer lacking one of its lines is a
        draft."""
        if Section.APPLIED in sections:
            return cls.APPLIED
        if Section.ANSWER not in sections:
            return cls.OPEN
        return cls.ANSWERED if all(field in given for field in ANSWER_FIELDS) else cls.DRAFT

    @property
    def waits(self) -> bool:
        """It waits for a person: no answer, or an incomplete one."""
        return self in WAITING

    @property
    def answered(self) -> bool:
        """It carries the person's answer: answered, or applied by a stage since."""
        return self in ANSWERED_STATES


class Section(enum.Enum):
    """The sections of a record its state follows from."""

    ANSWER = "answer"
    APPLIED = "applied"


class AnswerField(Value):
    """A line a confirmed answer carries: `answer:`, `by:`, `at:`."""

    value: str


#: The lines an answer carries before it counts: what was answered, by whom, when.
ANSWER_FIELDS = (AnswerField("answer"), AnswerField("by"), AnswerField("at"))


#: A record waits for a person while it has no answer or an incomplete one.
WAITING = frozenset((DecisionState.OPEN, DecisionState.DRAFT))
#: A record carries the person's answer once answered, and still after a stage applied it.
ANSWERED_STATES = frozenset((DecisionState.ANSWERED, DecisionState.APPLIED))


class Asker(enum.Enum):
    """Who asked: a stage of a story's run, or the skill a person's request ran (`request:` in the record)."""

    STAGE = "stage"
    REQUEST = "request"


class RecordKind(enum.Enum):
    """A question with options, or an acceptance — a look at a delivered story, answered `accepted` or corrected."""

    QUESTION = "question"
    ACCEPTANCE = "acceptance"


class Given(Value):
    """What a person answered: an option's key or their words, as written."""

    value: str

    def accepts(self) -> bool:
        """An answer that accepts a delivery: it begins with `accept` — `accepted`, `Accepted.`, `accept, thanks`."""
        return self.value.strip().lower().startswith("accept")


#: The answer an acceptance takes where the person accepts the delivery.
ACCEPTED = Given("accepted")


class Answer(Value):
    """The person's answer, who gave it and when."""

    given: Given
    by: Person
    at: Moment


class QuestionAnswered(DomainEvent):
    """A person answered a question a run could not answer itself."""

    record: RecordId
    story: typing.Optional[StoryId]
    at: Moment


class DeliveryAccepted(DomainEvent):
    """A person looked at a delivered story and accepted it."""

    record: RecordId
    story: typing.Optional[StoryId]
    at: Moment


class CorrectionAsked(DomainEvent):
    """A person looked at a delivered story and asked for a correction."""

    record: RecordId
    story: typing.Optional[StoryId]
    at: Moment


class AcceptanceAsked(DomainEvent):
    """Every gate passed and the story waits for a person's look before it counts as delivered."""

    record: RecordId
    story: StoryId
    at: Moment


#: The stage an acceptance is asked at: the one that delivers.
ACCEPTANCE_STAGE = StageName("document")


class AnswerApplied(DomainEvent):
    """A stage applied the person's answer: the record says by which, and when."""

    record: RecordId
    story: typing.Optional[StoryId]
    stage: StageName
    at: Moment


class Applied(Value):
    """Which stage applied the answer, and when."""

    stage: StageName
    at: Moment


class NotAnswered(DomainException):
    """Only an answered record is applied: one that waits has nothing to apply, one applied is applied once."""

    def __init__(self, record: RecordId, state: DecisionState) -> None:
        super().__init__(f"{record.value} is {state.value} — only an answered record is applied")
        self.record = record


class AlreadyAnswered(DomainException):
    """An answer is never overwritten — a change of mind is a new question."""

    def __init__(self, record: RecordId, state: DecisionState) -> None:
        super().__init__(f"{record.value} is {state.value} already — an answer is never overwritten; a change of "
                         "mind is a new question")


class NotOpen(DomainException):
    """An option is chosen on an open record only: one with an answer, complete or not, is not chosen on again."""

    def __init__(self, record: RecordId, state: DecisionState) -> None:
        super().__init__(f"{record.value} is {state.value} — an option is chosen on an open record")
        self.record = record


class OptionNotOffered(DomainException):
    """An option is one the record offers."""

    def __init__(self, record: RecordId, option: OptionKey, offered: typing.Sequence[OptionKey]) -> None:
        super().__init__(f"{record.value} offers {', '.join(o.value for o in offered) or 'no option'}, "
                         f"not {option.value}")
        self.record = record
        self.option = option


class NoAcceptance(DomainException):
    """Only an acceptance is accepted."""

    def __init__(self, record: RecordId) -> None:
        super().__init__(f"{record.value} asks a question, not for an acceptance")


class RecordContent(Value):
    """What a record says, read-only: its question, the stage that asked it (while it waits) or applies its answer,
    the answer and who gave it as written, and the answer lines a draft lacks."""

    question: Detail
    stage: typing.Optional[StageName]
    written_answer: Detail
    written_by: Detail
    missing: typing.Tuple[AnswerField, ...]
    #: the options with their first lines, as the record's `## Options` offers them
    option_lines: typing.Tuple[OptionLine, ...] = ()


class DecisionRecord(AggregateRoot[RecordId]):
    """A question beside its story, or the project's own: its options, who asked, its state and its answer, and what
    it says (`content`, read-only — what the gate reads)."""

    def __init__(self, record_id: RecordId, kind: RecordKind, asker: Asker, state: DecisionState,
                 options: typing.Sequence[OptionKey] = (), story: typing.Optional[StoryId] = None,
                 answer: typing.Optional[Answer] = None, *, content: RecordContent) -> None:
        super().__init__()
        self._content = content
        self._id = record_id
        self._kind = kind
        self._asker = asker
        self._state = state
        self._options = tuple(options)
        self._story = story
        self._answer = answer
        self._applied: typing.Optional[Applied] = None
        self._asked: typing.Optional[Moment] = None

    @classmethod
    def restore(cls, record_id: RecordId, kind: RecordKind, asker: Asker, state: DecisionState,
                options: typing.Sequence[OptionKey] = (), story: typing.Optional[StoryId] = None,
                answer: typing.Optional[Answer] = None, *, content: RecordContent) -> DecisionRecord:
        """The decision record as it was kept — the one way a repository builds it."""
        return cls(record_id, kind, asker, state, options, story, answer, content=content)

    @property
    def id(self) -> RecordId:
        return self._id

    @property
    def kind(self) -> RecordKind:
        return self._kind

    @property
    def asker(self) -> Asker:
        return self._asker

    @property
    def state(self) -> DecisionState:
        return self._state

    @property
    def options(self) -> typing.Tuple[OptionKey, ...]:
        return self._options

    @property
    def story(self) -> typing.Optional[StoryId]:
        return self._story

    @property
    def answer_given(self) -> typing.Optional[Answer]:
        return self._answer

    @classmethod
    def ask_acceptance(cls, record_id: RecordId, story: StoryId, at: Moment) -> DecisionRecord:
        """A new acceptance: open, asked at the delivering stage, for a person's look at the story."""
        record = cls(record_id, RecordKind.ACCEPTANCE, Asker.STAGE, DecisionState.OPEN, (), story,
                     content=RecordContent(Detail(f"Accept {story.value}?"), ACCEPTANCE_STAGE, Detail(""), Detail(""),
                                           ANSWER_FIELDS))
        record._asked = at
        record.register_event(AcceptanceAsked(record_id, story, at))
        return record

    @property
    def asked(self) -> typing.Optional[Moment]:
        """When a new record was asked in this life of it — None for one read as it was kept."""
        return self._asked

    @property
    def applied(self) -> typing.Optional[Applied]:
        """The stage that applied the answer in this life of the record, and when — None where none did."""
        return self._applied

    @property
    def content(self) -> RecordContent:
        """What the record says — its question, the stage, the answer as written."""
        return self._content

    def waits(self) -> bool:
        """Whether it still waits for a person: open, or a draft answer nobody signed."""
        return self._state in WAITING

    def answer_said(self) -> Detail:
        """The answer and who gave it, as a finding quotes them — the one it took, else the one written."""
        if self._answer is not None:
            return Detail(f"{self._answer.given.value!r} by {self._answer.by.value}")
        return Detail(f"{self._content.written_answer.value!r} by {self._content.written_by.value}")

    def given(self) -> typing.Optional[Given]:
        """What the person answered — None while it waits for one."""
        if self._answer is not None:
            return self._answer.given
        return Given(self._content.written_answer.value) if self._state.answered else None

    def answer_sentence(self) -> typing.Optional[Detail]:
        """The sentence the answer leaves in its story — deterministic: where the answer names an option by its label,
        that option's first line; else the answer itself. One line, emphasis and runs of white space taken out. None
        while the record waits."""
        given = self.given()
        if given is None:
            return None
        said = " ".join(given.value.replace("**", "").split())
        label = LABEL.match(said)
        if label:
            named = next((o.line for o in self._content.option_lines
                          if o.key.value.lower() == label.group(1).lower()), None)
            if named is not None:
                return named
        return Detail(said)

    def accepts(self) -> bool:
        """An acceptance the person answered with `accept…`: the delivery is what they wanted."""
        given = self.given()
        return self._kind is RecordKind.ACCEPTANCE and given is not None and given.accepts()

    def corrects(self) -> bool:
        """An acceptance answered with anything but `accept…`: the person asks for a correction."""
        return self._kind is RecordKind.ACCEPTANCE and self._state.answered and not self.accepts()

    def backs_change(self) -> bool:
        """An answer that backs a change of what holds: a question answered, or an acceptance's correction — never
        an acceptance that accepted."""
        if self._kind is RecordKind.ACCEPTANCE:
            return self.corrects()
        return self._state.answered

    def answer(self, answer: Answer) -> None:
        """The person's answer, once: a record answered or applied takes no second one."""
        if self._state in ANSWERED_STATES:
            raise AlreadyAnswered(self._id, self._state)
        self._answer = answer
        self._state = DecisionState.ANSWERED
        if self._kind is RecordKind.QUESTION:
            self.register_event(QuestionAnswered(self._id, self._story, answer.at))
        elif answer.given.accepts():
            self.register_event(DeliveryAccepted(self._id, self._story, answer.at))
        else:
            self.register_event(CorrectionAsked(self._id, self._story, answer.at))

    def apply(self, stage: StageName, at: Moment) -> None:
        """A stage applied the person's answer: the record is applied, by that stage."""
        if self._state is not DecisionState.ANSWERED:
            raise NotAnswered(self._id, self._state)
        self._state = DecisionState.APPLIED
        self._applied = Applied(stage, at)
        self.register_event(AnswerApplied(self._id, self._story, stage, at))

    def choose(self, option: OptionKey, by: Person, at: Moment) -> None:
        """A person's choice among the options of an open record — the option is the whole answer."""
        if self._state is not DecisionState.OPEN:
            raise NotOpen(self._id, self._state)
        if option not in self._options:
            raise OptionNotOffered(self._id, option, self._options)
        self.answer(Answer(Given(option.value), by, at))

    def accept(self, by: Person, at: Moment) -> None:
        """An acceptance answered `accepted`: the delivery is what the person wanted."""
        if self._kind is not RecordKind.ACCEPTANCE:
            raise NoAcceptance(self._id)
        self.answer(Answer(ACCEPTED, by, at))
