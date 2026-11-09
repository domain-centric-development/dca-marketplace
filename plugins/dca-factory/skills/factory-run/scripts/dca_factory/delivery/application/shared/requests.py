"""A person's request as the application handles it: what it may name, its repository and its read model.

A request is an asynchronous command arriving as a file (WP-91): a press on the page, `factory.sh request`, a
session's view. It is an aggregate of delivery (`domain/model/request.py`): two processes change one request — the
page and the cli queue it, the runner takes, parks, fails, queues again and settles it — so every change of its state
is one of the aggregate's operations, saved through the `RequestRepository` with its events. Deleted once done, it
carries a use case's command until the factory works it. Its states — queued, running, waiting, failed — are
`RequestState`'s; what it asks is read as `RequestFacts`, the read model listings and the runner read.

Every kind names what it is about in its own key — `story:`, `epic:`, `record:`, `topic:` with `proposal:` — and the
person's words, where it takes any, are the body. `option:` carries an option key (an answer's, a correction's code).
"""

from __future__ import annotations

import dataclasses
import re
import typing

from ....building_blocks import (DomainEventPublisher, OutputPort, Repository, Store, TransactionBoundary,
                                 UseCaseException)
from ...domain.model.project_path import ProjectPath
from ...domain.model.request import Request, RequestId, RequestOperation, RequestState
from ...domain.model.handed_file import FileRefused, HandedFileId
from ...domain.model.reach import Network, Reach

#: A request as the store reads it — a read model: its front keys, `id`, `path`, `words` (the body) and `state`,
#: strings all. What it asks is read here; where it stands is decided by the aggregate `Request`.
RequestFacts = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class Kind:
    """One kind of request: what it must name, whether it takes words, and the skill a session would run for it —
    none for the two the runner works itself (`run`, `stop`)."""

    name: str
    keys: typing.Tuple[str, ...] = ()   #: the keys it must name — `story`, `epic`, `record`, `topic`, `proposal`
    may: typing.Tuple[str, ...] = ()    #: the keys it may name — a discovery the topic it continues
    words: str = "none"                 #: the person's words: "required", "optional" or "none"
    option: bool = False                #: it takes `option:` — an answer's option key, a correction's reason code
    skill: str = ""                     #: the skill a session would run; "" — the runner works it itself
    about: str = ""
    creates: bool = False               #: whether an agent writes something new for it — a draft, an epic, a report
    web: bool = False                   #: whether its skill researches the web — the one request a network is for (WP-184)

    @property
    def reach(self) -> Reach:
        """What its skill's run may reach: offline, or the web for a skill that researches it."""
        return Reach.request(Network.RESEARCH if self.web else Network.NONE)


KINDS = (
    Kind("wish", words="required", skill="factory-backlog", creates=True,
         about="the person's words become a backlog item — a story, a task, a finding settled — kept as a draft"),
    Kind("release", keys=("story|epic",), skill="factory-backlog",
         about="release drafts — stories by id, or every draft of an epic — where the question pass leaves nothing open"),
    Kind("stories", keys=("epic",), skill="factory-backlog", creates=True, about="cut the next stories of an epic, as drafts"),
    Kind("journey", keys=("epic",), skill="factory-backlog", creates=True, about="propose the journey of a delivered epic"),
    Kind("describe", words="required", skill="description", creates=True,
         about="a change to the project description, in the person's words (`<part>: <change>`)"),
    Kind("discover", words="required", may=("topic",), skill="factory-discover", creates=True, web=True,
         about="a problem or a wished deliverable — the discovery report and the epics it proposes"),
    Kind("epic-from", keys=("topic", "proposal"), skill="factory-backlog", creates=True,
         about="a discovery's proposed epic, released as an epic"),
    Kind("answer", keys=("record",), words="optional", option=True, skill="factory-decisions",
         about="the answer to an open question — an option key or the person's words"),
    Kind("accept", keys=("story",), skill="factory-decisions", about="accept a story that waits for a person's look"),
    Kind("correct", keys=("story",), words="required", option=True, skill="factory-decisions",
         about="a correction of a story at its acceptance or after its delivery — `option:` the reason code"),
    Kind("run", keys=("story",), about="run a story now — from where its files say, or `from:` a stage"),
    Kind("stop", about="the factory ends after the running stage"),
)


KIND = {kind.name: kind for kind in KINDS}


def named_files(requests: typing.Iterable["RequestFacts"]) -> typing.List[HandedFileId]:
    """The handed files the requests name (WP-184) — an id of the wrong form is no file of theirs."""
    found = []
    for request in requests:
        for word in str(request.get("files") or "").split():
            try:
                found.append(HandedFileId(word))
            except FileRefused:
                continue
    return found


#: A story, an epic, a record, a topic or a proposal as a request names it: one word, no path.
ID_WORD = re.compile(r"^[A-Za-z0-9][\w.#-]*$")


#: The states a request's file says: every state but done — a done request has no file.
STATES = tuple(state.value for state in RequestState if state is not RequestState.DONE)

#: The states of a request that is not done: written, taken, or asking a person back.
PENDING = ("queued", "running", "waiting")


def operations_of(state: str) -> typing.List[str]:
    """What a person can do with a request in this state — `factory.sh requests --retry/--drop`, the page's buttons."""
    return [operation.value for operation in RequestState(state).operations()] if state in STATES \
        else [RequestOperation.DROP.value]


#: Where a question a request's skill asks back is answered: beside what the request was about — a discovery's on the
#: discover tab, the description's on describe —; every other on decide, beside the stories.
PLACE_OF_KIND = {"discover": "discover", "describe": "describe"}


def place_of(request_id: str) -> str:
    """The tab a record of the request <request_id> is answered on — `decide` for a stage's record or another kind."""
    kind = request_id.split("Z-", 1)[1] if "Z-" in request_id else ""
    return PLACE_OF_KIND.get(kind, "decide")


def written_keys(kind: Kind) -> typing.Set[str]:
    """The keys a person gives a request of this kind — what the check takes; the rest it adds from the files."""
    return {key for spec in kind.keys for key in spec.split("|")} | set(kind.may) | ({"option"} if kind.option else set()) \
        | ({"from"} if kind.name == "run" else set())


def stories_of(request: RequestFacts) -> typing.Set[str]:
    """The stories a request changes or runs — what must not run while it is worked, and the reverse."""
    return set(str(request.get("story") or "").split())


class RequestRefused(UseCaseException):
    """A request that cannot be written or read, with the reason a person reads."""


class DuplicateRequest(RequestRefused):
    """The same request is queued already — a second press, not a second wish."""

    def __init__(self, existing: str) -> None:
        super().__init__(f"the same request is queued already: {existing}")
        self.existing = existing


class RequestStore(Store, typing.Protocol):
    """The requests read, one file each, oldest first — the order the factory works them in —, a new one written, and
    what has no life cycle beside them: the journal and the notes of worked requests. Where a request stands changes
    through the `RequestRepository` alone."""

    def all(self) -> typing.List[RequestFacts]:
        ...

    def find(self, request_id: str) -> RequestFacts:
        """The request with this id; RequestRefused where there is none."""
        ...

    def add(self, kind: str, fields: typing.Mapping[str, str], words: str, by: str) -> typing.Tuple[str, str]:
        """Write a queued request, later than every request there: (id, path)."""
        ...

    def where(self) -> str:
        """The store's folder, as a person reads it."""
        ...

    def shown(self, request: RequestFacts) -> str:
        """Where the request is kept, as a person reads it."""
        ...

    def journal(self, *fields: str) -> None:
        """One line of the request journal: what happened to a request, when."""
        ...

    def keep_done(self, request: RequestFacts, wrote: str, commit: str, at: str) -> None:
        """A note of a worked request that wrote something new — its words, who asked, what it wrote and its commit —,
        kept beside the queue until a person releases what it made or hides it."""
        ...

    def done(self) -> typing.List[RequestFacts]:
        """The notes of worked requests, newest first, `state: done`."""
        ...

    def hide_done(self, request_id: str) -> bool:
        """The note of a worked request gone; False where there is none."""
        ...


class MadeItems(OutputPort, typing.Protocol):
    """What a request wrote, read back as the backlog's: the stories, tasks, epics and findings at those paths."""

    def at(self, paths: typing.Sequence[str]) -> typing.List[typing.Dict[str, str]]:
        """Per item it finds: kind (story, task, epic, finding), id, title, status — in the order of the paths."""
        ...


class RequestRepository(Repository[Request, RequestId], typing.Protocol):
    """The requests as aggregates: where each stands. A save writes its state into its file and keeps what it asks; a
    done request's file goes; one dropped meanwhile stays gone — unless the factory took it away itself, then the
    save writes it back."""

    def get(self, request_id: RequestId) -> Request:
        """The request with this id; RequestRefused where there is none."""
        ...

    def every(self) -> typing.List[Request]:
        """Every request, oldest first."""
        ...


def paths(text: str) -> typing.Tuple[ProjectPath, ...]:
    """The paths a request wrote, as a space-separated list names them."""
    return tuple(ProjectPath(path) for path in text.split())


class RequestKeeping:
    """A request's change kept: saved, and its events published, in one transaction — as every aggregate's."""

    def __init__(self, repository: RequestRepository, events: DomainEventPublisher,
                 transactions: TransactionBoundary) -> None:
        self._repository = repository
        self._events = events
        self._transactions = transactions

    def keep(self, request: Request) -> None:
        def save() -> None:
            self._repository.save(request)
            self._events.publish_and_clear_events(request)

        self._transactions.in_transaction(save)
