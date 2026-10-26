"""A decision record: a question a run may not answer itself, and the person's answer."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import AggregateRoot, DomainException, Id, Value
from .moment import Moment
from .person import Person
from .story import StoryId


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
#: The same as the words a record's state is read and shown with.
WAITING_WORDS = frozenset(state.value for state in WAITING)
ANSWERED_WORDS = frozenset(state.value for state in ANSWERED_STATES)


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


#: The answer an acceptance takes where the person accepts the delivery.
ACCEPTED = Given("accepted")


class Answer(Value):
    """The person's answer, who gave it and when."""

    given: Given
    by: Person
    at: Moment


class AlreadyAnswered(DomainException):
    """An answer is never overwritten — a change of mind is a new question."""

    def __init__(self, record: RecordId, state: DecisionState) -> None:
        super().__init__(f"{record.value} is {state.value} already — an answer is never overwritten; a change of "
                         "mind is a new question")


class NoAcceptance(DomainException):
    """Only an acceptance is accepted."""

    def __init__(self, record: RecordId) -> None:
        super().__init__(f"{record.value} asks a question, not for an acceptance")


class DecisionRecord(AggregateRoot[RecordId]):
    """A question beside its story, or the project's own: its options, who asked, its state and its answer."""

    def __init__(self, record_id: RecordId, kind: RecordKind, asker: Asker, state: DecisionState,
                 options: typing.Sequence[OptionKey] = (), story: typing.Optional[StoryId] = None,
                 answer: typing.Optional[Answer] = None) -> None:
        super().__init__()
        self._id = record_id
        self._kind = kind
        self._asker = asker
        self._state = state
        self._options = tuple(options)
        self._story = story
        self._answer = answer

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

    def answer(self, answer: Answer) -> None:
        """The person's answer, once: a record answered or applied takes no second one."""
        if self._state in ANSWERED_STATES:
            raise AlreadyAnswered(self._id, self._state)
        self._answer = answer
        self._state = DecisionState.ANSWERED

    def accept(self, by: Person, at: Moment) -> None:
        """An acceptance answered `accepted`: the delivery is what the person wanted."""
        if self._kind is not RecordKind.ACCEPTANCE:
            raise NoAcceptance(self._id)
        self.answer(Answer(ACCEPTED, by, at))
