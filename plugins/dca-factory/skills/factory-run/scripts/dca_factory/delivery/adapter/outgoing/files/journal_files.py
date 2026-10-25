"""Each story's journal as a file: `<evidence>/<story>/journal.tsv`, one event a line, numbered (`seq=`) — the
story's record. One writer at a time on a journal; a line from before sequence numbers takes its position."""

from __future__ import annotations

import contextlib
import glob
import os
import time
import typing

from .story_layout import find_story, story_digest, story_id_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, JOURNAL, place
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter, read_text
from ....application.shared.story_claims import ClaimHeld
from ....application.shared.story_journal import Window
from ....application.shared.story_repository import StoryNotFound
from ....domain.model.story import StoryId
from ....domain.model.usage import Usage, USAGE_FIELDS

#: One event of a journal: its `seq`, `at`, `kind`, `name`, `fields` and the `line` as written.
Event = typing.Dict[str, typing.Any]


def journal_path(runs: str, story_id: str) -> str:
    return os.path.join(evidence_dir(runs, story_id), JOURNAL)


def journal_events(runs: str, story_id: str) -> typing.List[Event]:
    """[{seq, at, kind, name, fields}] in order. A line from before sequence numbers takes its position."""
    return read_events(journal_path(runs, story_id))


def read_events(path: str) -> typing.List[Event]:
    events: typing.List[Event] = []
    if not os.path.isfile(path):
        return events
    for position, line in enumerate(read_text(path).splitlines(), 1):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        seq = fields.pop("seq", "")
        events.append({"seq": int(seq) if seq.isdigit() else position, "at": parts[0], "kind": parts[1],
                       "name": parts[2], "fields": fields, "line": line})
    # A union merge of two branches that ran the same story can repeat a number: the time decides between them.
    events.sort(key=lambda e: (e["seq"], e["at"]))
    return events


def flaky_tests(runs: str, story_id: str) -> typing.Dict[str, typing.List[str]]:
    """{test: [stage, …]} — the tests a gate over this story noted flaky (WP-113: red in a whole suite run, outside the
    story's change, green on its own run), from the journal's `gate` events and their `flaky=` field."""
    found: typing.Dict[str, typing.List[str]] = {}
    for event in journal_events(runs, story_id):
        if event["kind"] == "gate" and event["fields"].get("flaky"):
            for test in event["fields"]["flaky"].split(","):
                if test and event["name"] not in found.setdefault(test, []):
                    found[test].append(event["name"])
    return found


@contextlib.contextmanager
def journal_lock(path: str) -> typing.Iterator[None]:
    """One writer at a time on a journal: parallel reviewers and a stage's own gate append beside the runner. A
    folder is made atomically on every platform; one left by a killed process is taken over after half a minute."""
    lock = path + ".lock"
    deadline = time.time() + 10
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(lock) > 30:
                    os.rmdir(lock)
                    continue
            if time.time() > deadline:
                break                               # never block a run on a stale lock: append unlocked
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.rmdir(lock)


def journal_append(runs: str, story_id: str, kind: str, name: str, *fields: typing.Any,
                   at: typing.Optional[str] = None) -> int:
    """Append one event with the next sequence number; returns it."""
    return append_event(journal_path(runs, story_id), kind, name, *fields, at=at)


def append_event(path: str, kind: str, name: str, *fields: typing.Any, at: typing.Optional[str] = None) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with journal_lock(path):
        seq = 1 + max((e["seq"] for e in read_events(path)), default=0)
        stamp = at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cells = [stamp, kind, name] + [str(f) for f in fields if str(f)] + [f"seq={seq}"]
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in cells) + "\n")
    return seq


class journal_writer:
    """`with journal_writer(runs, story) as handle: handle.write("<time>\t<kind>\t<name>\t…\n")` — the old
    append idiom, every line through `journal_append`, so a writer that composes its lines keeps doing so."""

    def __init__(self, runs: str, story_id: str) -> None:
        self.runs, self.story_id = runs, story_id

    def __enter__(self) -> journal_writer:
        return self

    def __exit__(self, *_exc: typing.Any) -> typing.Literal[False]:
        return False

    def write(self, text: str) -> None:
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                journal_append(self.runs, self.story_id, parts[1], parts[2], *parts[3:], at=parts[0])


#: The mark a request that wrote drafts leaves in each one's journal: its question pass ran on the story as it stands.
QUESTIONED = "questioned"


def mark_questioned(cwd: str, runs: str, paths: typing.Iterable[str], request_id: str) -> None:
    """After a request whose skill wrote drafts and asked what they left open (a wish, the next stories): each draft
    it wrote carries `questioned digest=<story digest>` in its journal — the pass a release would run again."""
    for path in paths:
        full = os.path.join(cwd, path)
        if os.path.basename(path) != "story.md" or not os.path.isfile(full):
            continue
        with contextlib.suppress(MarkdownError):
            if str(read_front_matter(full)[0].get("status", "")).strip() == "draft":
                journal_append(runs, story_id_of(full), QUESTIONED, "backlog", f"digest={story_digest(full)}",
                               f"request={request_id}")


class StoryJournalFiles:
    """The story journal as files, in the run folder the profile places."""

    def __init__(self, cwd: str, runs: str) -> None:
        self._runs = runs
        self._epics = os.path.join(cwd, place("epics"))

    def question_pass_ran(self, story: StoryId) -> bool:
        try:
            path = find_story(self._epics, story.value)
        except MarkdownError as error:
            raise StoryNotFound(f"no story {story.value} under {place('epics')}/ — {error}") from None
        marks = [e for e in journal_events(self._runs, story.value) if e["kind"] == QUESTIONED]
        return bool(marks) and marks[-1]["fields"].get("digest") == story_digest(path)

    def windows_opened_by(self, request: str) -> typing.Sequence[Window]:
        windows = []
        for path in sorted(glob.glob(journal_path(self._runs, "*"))):
            story = os.path.basename(os.path.dirname(path))
            windows += [Window(StoryId(story), e["name"]) for e in read_events(path)
                        if e["kind"] == "window-start" and e["fields"].get("request") == request]
        return windows

    def book(self, window: Window, usage: Usage, tool: str, request: str) -> None:
        tokens = dict(input=usage.tokens.input, cache_read=usage.tokens.cache_read,
                      cache_write=usage.tokens.cache_write, output=usage.tokens.output)
        cells = [f"tool={tool}", f"request={request}", f"model={usage.model.value}"]
        cells += [f"{k}={tokens[k].value}" for k in USAGE_FIELDS]
        if usage.cost is not None:
            cells.append(f"cost={usage.cost.value:.4f}")
        journal_append(self._runs, window.story.value, "usage", window.name, *cells)

    def delivered_over_claim(self, story: StoryId, who: str) -> None:
        with contextlib.suppress(OSError):
            journal_append(self._runs, story.value, "note", "deliver-by-hand", f"over-claim={who}", "forced=1")

    def owned_confirmed(self, story: StoryId, parts: typing.Sequence[str]) -> None:
        journal_append(self._runs, story.value, "owned-confirmed", ",".join(parts))

    def claimed_elsewhere(self, story: StoryId, held: ClaimHeld) -> None:
        with contextlib.suppress(OSError):
            journal_append(self._runs, story.value, "note", "claimed-elsewhere", f"by={held.who}",
                           f"since={held.since}")
