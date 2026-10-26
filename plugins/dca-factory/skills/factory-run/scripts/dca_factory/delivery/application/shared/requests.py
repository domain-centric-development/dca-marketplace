"""A person's request: what it may name and where it stands — the application's, not the model's.

A request is an asynchronous command arriving as a file (WP-91): a press on the page, `factory.sh request`, a
session's view. It is no term of the model — deleted once done, it carries a use case's command until the factory
works it. While it lives, its state says where it is:

    queued    written, nobody took it yet
    running   a factory works it (`worker:`, `started:`)
    waiting   the skill it ran asked a person: a decision record names it (`request: <id>`), `record:` says which;
              answered, the request runs again with the answer
    failed    refused when it was read, or its skill ended without a result (`error:`); a person drops or retries it

Every kind names what it is about in its own key — `story:`, `epic:`, `record:`, `topic:` with `proposal:` — and the
person's words, where it takes any, are the body. `option:` carries an option key (an answer's, a correction's code).
"""

from __future__ import annotations

import dataclasses
import enum
import re
import typing

from ....building_blocks import Store, UseCaseException

#: A request as the store keeps it: its front keys, `id`, `path`, `words` (the body) and `state` — strings all.
Request = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class Kind:
    """One kind of request: what it must name, whether it takes words, and the skill a session would run for it —
    none for the two the runner works itself (`run`, `stop`)."""

    name: str
    keys: typing.Tuple[str, ...] = ()   #: the keys it must name — `story`, `epic`, `record`, `topic`, `proposal`
    words: str = "none"                 #: the person's words: "required", "optional" or "none"
    option: bool = False                #: it takes `option:` — an answer's option key, a correction's reason code
    skill: str = ""                     #: the skill a session would run; "" — the runner works it itself
    about: str = ""


KINDS = (
    Kind("wish", words="required", skill="factory-backlog",
         about="the person's words become a backlog item — a story, a task, a finding settled — kept as a draft"),
    Kind("release", keys=("story|epic",), skill="factory-backlog",
         about="release drafts — stories by id, or every draft of an epic — where the question pass leaves nothing open"),
    Kind("stories", keys=("epic",), skill="factory-backlog", about="cut the next stories of an epic, as drafts"),
    Kind("journey", keys=("epic",), skill="factory-backlog", about="propose the journey of a delivered epic"),
    Kind("describe", words="required", skill="description",
         about="a change to the project description, in the person's words (`<part>: <change>`)"),
    Kind("discover", words="required", skill="factory-discover",
         about="a problem or a wished deliverable — the discovery report and the epics it proposes"),
    Kind("epic-from", keys=("topic", "proposal"), skill="factory-backlog",
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


#: A story, an epic, a record, a topic or a proposal as a request names it: one word, no path.
ID_WORD = re.compile(r"^[A-Za-z0-9][\w.#-]*$")


class RequestState(enum.Enum):
    """Where a request is — and what a person can do with it there: follow one that runs, queue a failed one again,
    take back one that does not run."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"

    def operations(self) -> typing.List[str]:
        return (["follow"] if self is RequestState.RUNNING else []) \
            + (["retry"] if self is RequestState.FAILED else []) \
            + (["drop"] if self is not RequestState.RUNNING else [])


STATES = tuple(state.value for state in RequestState)

#: The states of a request that is not done: written, taken, or asking a person back.
PENDING = ("queued", "running", "waiting")


def operations_of(state: str) -> typing.List[str]:
    """What a person can do with a request in this state — `factory.sh requests --retry/--drop`, the page's buttons."""
    return RequestState(state).operations() if state in STATES else ["drop"]


def written_keys(kind: Kind) -> typing.Set[str]:
    """The keys a person gives a request of this kind — what the check takes; the rest it adds from the files."""
    return {key for spec in kind.keys for key in spec.split("|")} | ({"option"} if kind.option else set()) \
        | ({"from"} if kind.name == "run" else set())


def stories_of(request: Request) -> typing.Set[str]:
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
    """The requests, one file each, oldest first — the order the factory works them in."""

    def all(self) -> typing.List[Request]:
        ...

    def find(self, request_id: str) -> Request:
        """The request with this id; RequestRefused where there is none."""
        ...

    def add(self, kind: str, fields: typing.Mapping[str, str], words: str, by: str) -> typing.Tuple[str, str]:
        """Write a queued request, later than every request there: (id, path)."""
        ...

    def update(self, request: Request, restore: bool = False, **fields: typing.Optional[str]) -> None:
        """Set — or with None remove — front keys; `restore` writes back one the factory took away itself."""
        ...

    def remove(self, request: Request) -> None:
        ...

    def where(self) -> str:
        """The store's folder, as a person reads it."""
        ...

    def shown(self, request: Request) -> str:
        """Where the request is kept, as a person reads it."""
        ...

    def journal(self, *fields: str) -> None:
        """One line of the request journal: what happened to a request, when."""
        ...
