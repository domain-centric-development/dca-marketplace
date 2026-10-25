"""The stories' worktrees: where they live, whether a story has one, and whether its file is on the main line."""

from __future__ import annotations

import os
import typing
from .....sharedkernel.adapter.outgoing.profile.profile_files import DEFAULTS, factory_home, PLACES_REL
from .repository import git


def worktrees_dir() -> str:
    """Where the stories' worktrees live, relative to the main checkout: beside the run folder."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).rstrip("/")
    return os.path.join(os.path.dirname(runs) or ".dca-factory", "worktrees").replace("\\", "/")


def worktree_of(story_id: str, home: typing.Optional[str] = None) -> str:
    """The story's worktree in the main checkout (here, unless FACTORY_HOME names another)."""
    return os.path.join(home or factory_home() or os.getcwd(), worktrees_dir(), story_id)


def has_worktree(story_id: str, home: typing.Optional[str] = None) -> bool:
    """Whether the story has its worktree: a checkout with git's `.git` file in it."""
    return os.path.isfile(os.path.join(worktree_of(story_id, home), ".git"))


def uncommitted_story(home: str, path: str, ref: str = "HEAD", changed: bool = True) -> str:
    """Why a story's file is not on the main line as the checkout has it — not in `ref`'s tree, or (with `changed`)
    changed since —, or "". A story's worktree starts from the main line's commit and the integrate step tests that
    tree: a story only the checkout holds is missing there, and the tests that read the backlog go red on the main
    line (#162). Outside a repository, before its first commit, or for a file outside the checkout, nothing is
    compared."""
    if git(home, "rev-parse", "--verify", "--quiet", ref)[0] != 0:
        return ""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(home)).replace(os.sep, "/")
    if rel.startswith("../"):
        return ""
    if git(home, "cat-file", "-e", f"{ref}:{rel}")[0] != 0:
        return f"{rel} is not committed"
    if changed and git(home, "diff", "--quiet", ref, "--", rel)[0] != 0:
        return f"{rel} changed since its last commit"
    return ""
