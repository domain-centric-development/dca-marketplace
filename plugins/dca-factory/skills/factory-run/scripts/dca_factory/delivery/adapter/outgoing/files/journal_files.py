"""Each story's journal as a file: `<evidence>/<story>/journal.tsv`, one event a line."""

from __future__ import annotations

import contextlib
import glob
import os
import typing

from .....contract import story_digest, story_id_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....state import journal_append, journal_events, journal_path, read_events
from ....application.shared.story_journal import Window
from ....domain.model.story import StoryId
from ....domain.model.usage import Usage, USAGE_FIELDS
from .story_files import StoryFiles

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
        self._stories = StoryFiles(cwd)

    def question_pass_ran(self, story: StoryId) -> bool:
        path = self._stories.path_of(story)
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
