"""The requests as files: `<factory folder>/requests/<stamp>-<kind>.md`, the stamp UTC to the millisecond, front
matter and the person's words as the body (WP-91); beside them the request journal and the tools' raw outputs."""

from __future__ import annotations

import contextlib
import getpass
import os
import re
import time
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from ..git.repository import git
from .....sharedkernel.adapter.outgoing.markdown.front_matter import (
    MarkdownError, read_front_matter, read_text, split_front)
from ....application.shared.requests import ID_WORD, KIND, Request, RequestRefused, STATES

REQUESTS = "requests"
REQUEST_JOURNAL = "journal.tsv"
REQUEST_OUT = "out"

#: The keys a request's front matter may carry, in the order they are written.
FRONT_KEYS = ("kind", "story", "epic", "record", "topic", "proposal", "report", "option", "from", "by", "asked",
              "state", "worker", "started", "attempts", "record_file", "error", "answered", "wrote",
              "worked")


def factory_dir() -> str:
    """The factory's own folder, the run folder's parent: `.dca-factory` by default."""
    runs = str(place("runs")).rstrip("/")
    return os.path.dirname(runs) or ".dca-factory"


def requests_dir() -> str:
    return os.path.join(factory_dir(), REQUESTS)


def request_path(request_id: str) -> str:
    return os.path.join(requests_dir(), f"{request_id}.md")


def out_path(request_id: str) -> str:
    """Where the tool's raw output of a request's run is kept: beside the requests, pruned with the run folders."""
    return os.path.join(requests_dir(), REQUEST_OUT, f"{request_id}.out")


def stamp_utc(moment: typing.Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))


def default_by(cwd: str) -> str:
    """Who asks, where nobody said: the repository's `user.name`, else the account's name."""
    code, name = git(cwd, "config", "user.name")
    if code == 0 and name.strip():
        return str(name.strip())
    with contextlib.suppress(Exception):
        return getpass.getuser()
    return "unknown"


def front_text(front: typing.Mapping[str, typing.Any]) -> str:
    lines = ["---"]
    for key in FRONT_KEYS:
        value = front.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {' '.join(str(value).split())}")
    return "\n".join(lines + ["---", ""])


def write_atomic(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def read_request(path: str) -> Request:
    """The request as a dict — its id, path, front keys, `words` (the body) and `state`; a file that cannot be read
    is `failed` with the reason, so a broken request shows and is never worked."""
    request_id = os.path.basename(path)[:-3]
    try:
        front, body = read_front_matter(path)
    except (MarkdownError, OSError, UnicodeDecodeError) as error:
        return dict(id=request_id, path=path, kind="?", words="", state="failed", error=f"unreadable — {error}")
    request: Request = {k: (" ".join(v) if isinstance(v, list) else str(v)).strip() for k, v in front.items()}
    request.update(id=request_id, path=path, words=body.strip())
    if request.get("kind") not in KIND:
        request.update(state="failed", error=request.get("error") or f"no request kind {request.get('kind')!r}")
    elif request.get("state") not in STATES:
        request["state"] = "queued"
    return request


def list_requests() -> typing.List[Request]:
    """Every request, oldest first — the order the factory works them in."""
    folder = requests_dir()
    if not os.path.isdir(folder):
        return []
    return [read_request(os.path.join(folder, name)) for name in sorted(os.listdir(folder))
            if name.endswith(".md") and not name.startswith(".")]


def find_request(request_id: str) -> Request:
    path = request_path(request_id)
    if not ID_WORD.match(request_id) or not os.path.isfile(path):
        raise RequestRefused(f"no request {request_id} — `factory.sh requests` lists them")
    return read_request(path)


def update_request(request: Request, restore: bool = False, **fields: typing.Optional[str]) -> None:
    """Set — or with None remove — front keys of a request, its words kept. `restore` writes it back where the
    factory took it away itself (a done request whose commit was refused); else one dropped meanwhile stays gone."""
    path = request["path"]
    try:
        if not restore and split_front(read_text(path)) is None:
            return
    except (MarkdownError, OSError, UnicodeDecodeError):
        return                                       # dropped meanwhile: nothing left to update
    front = {k: v for k, v in request.items() if k in FRONT_KEYS}
    for key, value in fields.items():
        if value is None:
            front.pop(key, None)
        else:
            front[key] = value
        request[key] = value
    write_atomic(path, front_text(front) + (f"\n{request['words']}\n" if request.get("words") else ""))


def write_request(cwd: str, kind: str, fields: typing.Mapping[str, str], words: str, by: str) -> typing.Tuple[str, str]:
    """A queued request, written — later than every request there: (id, path)."""
    folder = requests_dir()
    # to the millisecond, and later than every request there: the files sort in the order they were written,
    # whatever their kind — two in one millisecond included
    millis = int(time.time() * 1000)
    newest = max((n[:19] for n in os.listdir(folder) if re.match(r"^\d{8}T\d{9}Z", n)), default="") \
        if os.path.isdir(folder) else ""

    def stamp_of(ms: int) -> str:
        return time.strftime("%Y%m%dT%H%M%S", time.gmtime(ms // 1000)) + f"{ms % 1000:03d}Z"
    while stamp_of(millis) <= newest:
        millis += 1
    stamp = stamp_of(millis)
    request_id, n = f"{stamp}-{kind}", 1
    os.makedirs(folder, exist_ok=True)
    while True:
        path = os.path.join(folder, f"{request_id}.md")
        try:
            # created exclusively: two presses in one second get two names, never one file
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            n += 1
            request_id = f"{stamp}.{n}-{kind}"     # `.` sorts after `-`: the second of a second stays second
    front = dict(fields, kind=kind, by=" ".join((by or default_by(cwd)).split()), asked=stamp_utc(), state="queued")
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(front_text(front) + (f"\n{words}\n" if words else ""))
    return request_id, path


def journal(*fields: typing.Any) -> None:
    """One line of the factory's request journal — `<at>\\t<event>\\t…` — beside the requests."""
    os.makedirs(requests_dir(), exist_ok=True)
    with contextlib.suppress(OSError):
        with open(os.path.join(requests_dir(), REQUEST_JOURNAL), "a", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join([stamp_utc(), *(" ".join(str(f).split()) for f in fields)]) + "\n")


def journal_lines(limit: int = 50) -> typing.List[typing.List[str]]:
    path = os.path.join(requests_dir(), REQUEST_JOURNAL)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n").split("\t") for line in handle.readlines()[-limit:]]


def prune_outputs(days: int = 7, now: typing.Optional[float] = None) -> None:
    """The raw outputs of requests that ended more than <days> ago — protocol, kept for a look, not forever."""
    folder = os.path.join(requests_dir(), REQUEST_OUT)
    if not os.path.isdir(folder):
        return
    limit = (now or time.time()) - days * 86400
    live = {r["id"] for r in list_requests()}
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        with contextlib.suppress(OSError):
            if name.rsplit(".", 1)[0] not in live and os.path.getmtime(path) < limit:
                os.remove(path)


class RequestFiles:
    """The request store as files, relative to the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def all(self) -> typing.List[Request]:
        return list_requests()

    def find(self, request_id: str) -> Request:
        return find_request(request_id)

    def add(self, kind: str, fields: typing.Mapping[str, str], words: str, by: str) -> typing.Tuple[str, str]:
        return write_request(self._cwd, kind, fields, words, by)

    def update(self, request: Request, restore: bool = False, **fields: typing.Optional[str]) -> None:
        update_request(request, restore, **fields)

    def remove(self, request: Request) -> None:
        os.remove(request["path"])

    def where(self) -> str:
        return str(shown(requests_dir()))

    def shown(self, request: Request) -> str:
        return str(shown(request["path"]))

    def journal(self, *fields: str) -> None:
        journal(*fields)
