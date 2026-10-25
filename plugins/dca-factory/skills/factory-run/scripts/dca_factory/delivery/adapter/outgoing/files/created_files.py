"""The stories' and epics' `created:` lines as files, their first day from git."""

from __future__ import annotations

import contextlib
import os
import typing
from datetime import datetime, timezone

from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ....application.shared.created_stamps import Unstamped
from ....application.shared.front import CREATED_KEY
from ....domain.model.moment import Moment
from ..git.repository import git
from .epic_files import epic_files
from .owned_files import write_story_fields
from .story_layout import EPIC_FILE, story_files


def utc_text(moment: datetime) -> str:
    """A time as the backlog writes it: UTC, to the second, `Z`."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CreatedFiles:
    """The stories and epics under <epics>, in the project <cwd>."""

    def __init__(self, cwd: str, epics: str) -> None:
        self._cwd = cwd
        self._epics = epics

    def unstamped(self) -> typing.Sequence[Unstamped]:
        files = story_files(self._epics) + [os.path.join(self._epics, e["folder"], EPIC_FILE)
                                            for e in epic_files(self._epics)]
        found = []
        for path in files:
            try:
                front = read_front_matter(path)[0]
            except MarkdownError:
                continue
            if CREATED_KEY not in front:
                found.append(Unstamped(path, "epic" if os.path.basename(path) == EPIC_FILE else "story"))
        return found

    def first_added(self, path: str) -> typing.Optional[Moment]:
        rel = os.path.normpath(os.path.relpath(path, self._cwd))
        if git(self._cwd, "rev-parse", "--is-inside-work-tree")[0] != 0 \
                or git(self._cwd, "ls-files", "--error-unmatch", "--", rel)[0] != 0:
            return None
        code, out = git(self._cwd, "log", "--follow", "--diff-filter=A", "--format=%aI", "--", rel)
        lines = out.strip().splitlines() if code == 0 else []
        if not lines:
            return None
        with contextlib.suppress(ValueError):
            # the log is newest first: the earliest add
            return Moment(utc_text(datetime.fromisoformat(lines[-1].strip().replace("Z", "+00:00"))))
        return None

    def file_time(self, path: str) -> Moment:
        return Moment(utc_text(datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)))

    def stamp(self, path: str, created: Moment) -> None:
        write_story_fields(path, **{CREATED_KEY: created.value})
