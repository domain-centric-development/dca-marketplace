"""Where a folder sits in git, asked once (WP-202): a `Checkout` — its top, its git folder, the git folder its
worktrees share, the prefix of the folder it is entered from, its index — built in one `rev-parse` and handed to the
adapters that ask git where things are. Its lifetime is a run's, a gate call's or a cli call's (`Checkouts`), never
the process's: a folder that is no repository yet answers with the git folder of one above it, and an answer kept past
its `git init` would give it a checkout that is not its own."""

from __future__ import annotations

import os
import re
import subprocess
import typing

#: what a ref file or a detached HEAD holds: an object name (sha1 or sha256)
OBJECT_NAME = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


class Checkout(typing.NamedTuple):
    """One git checkout as seen from the folder it is entered from — every path absolute."""

    top: str
    git_dir: str
    common_dir: str
    prefix: str
    index_file: str

    def head(self) -> typing.Optional[str]:
        """HEAD's commit now, read from the git folder's files rather than asked of a process — HEAD moves with every
        commit, so it is never kept. None where the files do not say (a branch with no commit yet, a ref store other
        than files): the caller asks git then."""
        text = read_line(os.path.join(self.git_dir, "HEAD"))
        if text is None or OBJECT_NAME.match(text):
            return text
        if not text.startswith("ref: "):
            return None
        ref = text[len("ref: "):].strip()
        for folder in (self.git_dir, self.common_dir):
            named = read_line(os.path.join(folder, *ref.split("/")))
            if named is not None:
                return named if OBJECT_NAME.match(named) else None
        packed = os.path.join(self.common_dir, "packed-refs")
        try:
            with open(packed, encoding="utf-8") as handle:
                for line in handle:
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref and OBJECT_NAME.match(parts[0]):
                        return parts[0]
        except OSError:
            pass
        return None


def read_line(path: str) -> typing.Optional[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readline().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def checkout_of(folder: str) -> typing.Optional[Checkout]:
    """The checkout <folder> is in, from one `rev-parse` — None outside a repository. A folder below a repository's
    top is in that repository, its prefix saying where."""
    asked = subprocess.run(["git", "rev-parse", "--show-toplevel", "--absolute-git-dir", "--git-common-dir",
                            "--show-prefix", "--git-path", "index"], cwd=folder, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    lines = asked.stdout.split("\n")
    if asked.returncode != 0 or len(lines) < 5 or not lines[0].strip():
        return None
    here = os.path.abspath(folder)
    return Checkout(top=os.path.normpath(lines[0].strip()), git_dir=os.path.normpath(lines[1].strip()),
                    common_dir=os.path.normpath(os.path.join(here, lines[2].strip())), prefix=lines[3].strip(),
                    index_file=os.path.normpath(os.path.join(here, lines[4].strip())))


class Checkouts:
    """The checkouts one run, one gate call or one cli call stands in — each asked of git once, at the first question
    from its folder (`at`), or anew where the run enters it (`enter`: a story's worktree is its own checkout). Built by
    the composition root for that run or call and dropped with it; nothing outlives it."""

    def __init__(self) -> None:
        self._known: typing.Dict[str, typing.Optional[Checkout]] = {}

    def at(self, folder: str) -> typing.Optional[Checkout]:
        key = os.path.abspath(folder)
        if key not in self._known:
            self._known[key] = checkout_of(key)
        return self._known[key]

    def enter(self, folder: str) -> typing.Optional[Checkout]:
        """The checkout of a folder the run moves into — asked now, whatever an earlier question said of it."""
        self.leave(folder)
        return self.at(folder)

    def leave(self, folder: str) -> None:
        """A folder the run is done with — a removed worktree: a later question asks git again."""
        self._known.pop(os.path.abspath(folder), None)
