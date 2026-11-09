"""A person's request: an asynchronous command the factory works, and where it stands — one aggregate, since two
processes change it: the page and the cli queue it, the runner takes, parks, fails, queues again and settles it."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import AggregateRoot, DomainEvent, DomainException, Id, Value
from .claim import Worker
from .decision_record import RecordId
from .moment import Moment
from .project_path import ProjectPath
from .story import StoryId
from .story_words import Count


class RequestId(Id):
    """The name of one request: `<stamp>-<kind>`, its file's name."""

    value: str


class RequestOperation(enum.Enum):
    """What a person can do with a request: follow one that runs, queue a failed one again, take back one that does
    not run."""

    FOLLOW = "follow"
    RETRY = "retry"
    DROP = "drop"


class RequestState(enum.Enum):
    """Where a request is:

        queued    written, nobody took it yet
        running   a factory works it (its worker, since when)
        waiting   the skill it ran asked a person: a decision record names it, `record_file` says which; answered, it
                  runs again with the answer
        failed    refused when it was read, or its skill ended without a result (`error`); a person drops or retries it
        done      worked to its end — its file gone, a note of what it made kept where it made something
        dropped   taken back by a person before it ran or after it failed — its file gone
    """

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
    DONE = "done"
    DROPPED = "dropped"

    def operations(self) -> typing.Tuple[RequestOperation, ...]:
        return ((RequestOperation.FOLLOW,) if self is RequestState.RUNNING else ()) \
            + ((RequestOperation.RETRY,) if self is RequestState.FAILED else ()) \
            + ((RequestOperation.DROP,) if self not in (RequestState.RUNNING, RequestState.DONE, RequestState.DROPPED)
               else ())


#: The states a request in hand is in: not yet taken, or taken and not ended.
IN_HAND = frozenset((RequestState.QUEUED, RequestState.RUNNING))
QUEUED = frozenset((RequestState.QUEUED,))
RUNNING = frozenset((RequestState.RUNNING,))
WAITING = frozenset((RequestState.WAITING,))
FAILED = frozenset((RequestState.FAILED,))


class Why(Value):
    """Why a request failed, for a person."""

    value: str


class RequestNotInState(DomainException):
    """An operation the request's state does not allow — taken twice, parked while not running, retried while not
    failed."""


class NoRecord(DomainException):
    """A request waits only on the record that asks a person."""


class RequestQueued(DomainEvent):
    """A request is queued: written, or queued again — retried, answered, left running or stopped."""

    request: RequestId
    at: Moment
    story: typing.Optional[StoryId] = None


class RequestTaken(DomainEvent):
    """A worker took a queued request; its skill runs."""

    request: RequestId
    worker: Worker
    attempt: Count
    at: Moment
    story: typing.Optional[StoryId] = None


class RequestWaiting(DomainEvent):
    """The skill a request ran asked a person; the request waits for the answer."""

    request: RequestId
    record: ProjectPath
    at: Moment
    story: typing.Optional[StoryId] = None


class RequestFailed(DomainEvent):
    """A request failed: it no longer held, its skill ended without a result, or what it wrote was not committed."""

    request: RequestId
    at: Moment
    story: typing.Optional[StoryId] = None


class RequestSettled(DomainEvent):
    """A request is worked to its end: its file is gone."""

    request: RequestId
    at: Moment
    story: typing.Optional[StoryId] = None


class RequestDropped(DomainEvent):
    """A person took a request back: it never ran, waited or failed — its file is gone."""

    request: RequestId
    at: Moment
    story: typing.Optional[StoryId] = None


class Request(AggregateRoot[RequestId]):
    """A request's life: queued until one worker takes it, running until its skill ends — waiting where it asked a
    person, failed where it ended without a result, done where it did its part. Every change of its state is one of
    its operations, each guarded and raising its event; what it asks — its kind, what it names, the person's words —
    is not the aggregate's: it is read with it and never changed."""

    def __init__(self, request_id: RequestId, state: RequestState, *, worker: typing.Optional[Worker] = None,
                 started: typing.Optional[Moment] = None, attempts: Count = Count(0),
                 error: typing.Optional[Why] = None, record_file: typing.Optional[ProjectPath] = None,
                 answered: typing.Tuple[RecordId, ...] = (), wrote: typing.Tuple[ProjectPath, ...] = (),
                 worked: typing.Optional[Moment] = None) -> None:
        super().__init__()
        self._id = request_id
        self._state = state
        self._worker = worker
        self._started = started
        self._attempts = attempts
        self._error = error
        self._record_file = record_file
        self._answered = answered
        self._wrote = wrote
        self._worked = worked

    @classmethod
    def restore(cls, request_id: RequestId, state: RequestState, *, worker: typing.Optional[Worker] = None,
                started: typing.Optional[Moment] = None, attempts: Count = Count(0),
                error: typing.Optional[Why] = None, record_file: typing.Optional[ProjectPath] = None,
                answered: typing.Tuple[RecordId, ...] = (), wrote: typing.Tuple[ProjectPath, ...] = (),
                worked: typing.Optional[Moment] = None) -> Request:
        """The request as it was kept — the one way a repository builds it."""
        return cls(request_id, state, worker=worker, started=started, attempts=attempts, error=error,
                   record_file=record_file, answered=answered, wrote=wrote, worked=worked)

    @classmethod
    def written(cls, request_id: RequestId, at: Moment) -> Request:
        """A request just written: queued (`RequestQueued`)."""
        request = cls(request_id, RequestState.QUEUED)
        request.register_event(RequestQueued(request_id, at))
        return request

    @property
    def id(self) -> RequestId:
        return self._id

    @property
    def state(self) -> RequestState:
        return self._state

    @property
    def worker(self) -> typing.Optional[Worker]:
        return self._worker

    @property
    def started(self) -> typing.Optional[Moment]:
        return self._started

    @property
    def attempts(self) -> Count:
        return self._attempts

    @property
    def error(self) -> typing.Optional[Why]:
        return self._error

    @property
    def record_file(self) -> typing.Optional[ProjectPath]:
        return self._record_file

    @property
    def answered(self) -> typing.Tuple[RecordId, ...]:
        return self._answered

    @property
    def wrote(self) -> typing.Tuple[ProjectPath, ...]:
        return self._wrote

    @property
    def worked(self) -> typing.Optional[Moment]:
        return self._worked

    def queued(self) -> bool:
        """Nobody took it yet."""
        return self._state is RequestState.QUEUED

    def waiting(self) -> bool:
        """It asked a person and waits for the answer."""
        return self._state is RequestState.WAITING

    def in_hand(self) -> bool:
        """Queued or running: not ended."""
        return self._state in IN_HAND

    def orphaned_by(self, worker: Worker) -> bool:
        """Running for another worker than <worker>, which holds the claim now: the one that took it ended."""
        return self._state is RequestState.RUNNING and self._worker != worker

    def allows(self, operation: RequestOperation) -> bool:
        """Whether a person may do this with it in its state."""
        return operation in self._state.operations()

    def take(self, worker: Worker, at: Moment) -> None:
        """One worker takes a queued request — its next attempt, any earlier failure gone (`RequestTaken`)."""
        self._require(QUEUED)
        self._state = RequestState.RUNNING
        self._worker = worker
        self._started = at
        self._attempts = Count(self._attempts.value + 1)
        self._error = None
        self.register_event(RequestTaken(self._id, worker, self._attempts, at))

    def wait(self, record: ProjectPath, wrote: typing.Tuple[ProjectPath, ...], at: Moment) -> None:
        """A running request whose skill asked a person waits — on the record that asks, never without one
        (`RequestWaiting`)."""
        self._require(RUNNING)
        if not record.value:
            raise NoRecord(f"request {self._id.value} waits on a record — none was named")
        self._state = RequestState.WAITING
        self._worker = None
        self._record_file = record
        self._wrote = wrote
        self.register_event(RequestWaiting(self._id, record, at))

    def wake(self, answered: typing.Tuple[RecordId, ...], at: Moment) -> None:
        """A waiting request whose records are answered is queued again, with the answers to read (`RequestQueued`)."""
        self._require(WAITING)
        self._queue_again(at)
        self._record_file = None
        self._answered = answered

    def ask_again(self, at: Moment) -> None:
        """A waiting request whose record is gone is queued again: it runs and asks again (`RequestQueued`)."""
        self._require(WAITING)
        self._queue_again(at)
        self._record_file = None

    def requeue_orphan(self, worker: Worker, at: Moment) -> None:
        """A request another worker left running is queued again: <worker> holds the claim now (`RequestQueued`)."""
        self._require(RUNNING)
        if not self.orphaned_by(worker):
            raise RequestNotInState(f"request {self._id.value} runs for {worker.value} — no orphan")
        self._queue_again(at)
        self._worker = None
        self._started = None

    def requeue_stopped(self, at: Moment, wrote: typing.Optional[typing.Tuple[ProjectPath, ...]] = None) -> None:
        """A request whose process was stopped is queued for the next start — what it wrote so far kept, where given
        (`RequestQueued`)."""
        self._require(IN_HAND)
        self._queue_again(at)
        self._worker = None
        self._started = None
        if wrote is not None:
            self._wrote = wrote

    def retry(self, at: Moment) -> None:
        """A failed request is queued again, as it was written (`RequestQueued`)."""
        self._require(FAILED)
        self._queue_again(at)
        self._error = None
        self._worker = None
        self._started = None

    def fail(self, why: Why, at: Moment, wrote: typing.Optional[typing.Tuple[ProjectPath, ...]] = None) -> None:
        """A request in hand fails, saying why — what it wrote so far kept, where given (`RequestFailed`)."""
        self._require(IN_HAND)
        self._end_failed(why, at)
        if wrote is not None:
            self._wrote = wrote

    def leave_uncommitted(self, why: Why, wrote: typing.Tuple[ProjectPath, ...], at: Moment) -> None:
        """A request whose skill did its part and whose commit was refused fails, its work marked done (`worked`): a
        retry commits what it wrote and runs no skill again (`RequestFailed`)."""
        self._require(IN_HAND)
        self._end_failed(why, at)
        self._wrote = wrote
        self._worked = at

    def settle(self, at: Moment) -> None:
        """A request in hand is worked to its end: done, its file goes (`RequestSettled`)."""
        self._require(IN_HAND)
        self._state = RequestState.DONE
        self.register_event(RequestSettled(self._id, at))

    def drop(self, at: Moment) -> None:
        """A person takes back a request that does not run: its file goes (`RequestDropped`)."""
        if not self.allows(RequestOperation.DROP):
            raise RequestNotInState(f"request {self._id.value} is {self._state.value} — it can be dropped once it "
                                    "ended")
        self._state = RequestState.DROPPED
        self.register_event(RequestDropped(self._id, at))

    def _queue_again(self, at: Moment) -> None:
        self._state = RequestState.QUEUED
        self.register_event(RequestQueued(self._id, at))

    def _end_failed(self, why: Why, at: Moment) -> None:
        self._state = RequestState.FAILED
        self._worker = None
        self._error = why
        self.register_event(RequestFailed(self._id, at))

    def _require(self, states: typing.AbstractSet[RequestState]) -> None:
        if self._state not in states:
            raise RequestNotInState(f"request {self._id.value} is {self._state.value} — the operation wants it "
                                    + " or ".join(sorted(state.value for state in states)))
