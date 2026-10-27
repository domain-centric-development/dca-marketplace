"""What a request changed in the main checkout, as git sees it, and its commit through the commit hook."""

from __future__ import annotations

import hashlib
import os
import subprocess
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_rel
from ....application.shared.backlog_changes import Committed
from ..stack.commands import tail
from ..files.delivery_writes import story_journals
from .change import in_places, people_places
from .repository import git, git_identity


class BacklogChangeFiles:
    """The main checkout <home> with its run folder <runs>; <profile> sets the places as they stand, <lock> is the
    integrate lock a commit takes."""

    def __init__(self, home: str, runs: str, profile: typing.Callable[[], typing.Any],
                 lock: typing.Callable[[], typing.ContextManager[None]]) -> None:
        self._home = home
        self._runs = runs
        self._profile = profile
        self._lock = lock

    def dirty(self) -> typing.Dict[str, str]:
        # not through `git()`, which strips the answer: the first entry's leading blank is its status column
        done = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames"],
                              cwd=self._home, capture_output=True, text=True, encoding="utf-8", errors="replace")
        found: typing.Dict[str, str] = {}
        if done.returncode != 0:
            return found
        for entry in done.stdout.split("\0"):
            if len(entry) < 4:
                continue
            path = entry[3:]
            if path.startswith((self._runs.rstrip("/") + "/", evidence_rel() + "/", ".dca-factory/")):
                continue
            try:
                with open(os.path.join(self._home, path), "rb") as handle:
                    found[path] = hashlib.sha256(handle.read()).hexdigest()
            except OSError:
                found[path] = "deleted"
        return found

    def people(self, paths: typing.Iterable[str]) -> typing.Set[str]:
        self._profile()
        places = people_places()
        return {path for path in paths if in_places(path, places)}

    def commit(self, paths: typing.Sequence[str], message: str) -> Committed:
        paths = list(paths) + story_journals(self._home)   # what it did to a story is in that story's record too
        with self._lock():
            git(self._home, "add", "--", *paths)
            # through the commit hook, as a person's backlog commit: it runs what the profile's `checks.backlog:` names
            done = git(self._home, *git_identity(self._home), "commit", "--quiet", "-m", message, "--", *paths)
            if done[0] != 0:
                git(self._home, "reset", "--quiet", "--", *paths)
        if done[0] != 0:
            return Committed("", tail(done[1], 1500))
        return Committed(git(self._home, "rev-parse", "--short", "HEAD")[1].strip(), "")
