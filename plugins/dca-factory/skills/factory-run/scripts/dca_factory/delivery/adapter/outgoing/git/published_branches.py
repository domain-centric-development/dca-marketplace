"""A story's published branch in its worktree, its delivery taken back with git."""

from __future__ import annotations

import contextlib
import os

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home, place
from ....application.shared.published_branches import TakenBack
from ..claims.remote_claims import claim_config_here, fetch_remote, PUBLISHED, remote_main
from ..claims.story_claims import claim_target
from ..files.owned_files import write_story_fields
from ..files.story_layout import find_story
from .repository import git
from .worktrees import has_worktree, worktree_of


class PublishedBranchFiles:
    """The published branches of the checkout <cwd>, the stories under <epics>, the run folder <runs>."""

    def __init__(self, cwd: str, runs: str, epics: str) -> None:
        self._cwd = cwd
        self._runs = runs
        self._epics = epics

    def published(self, story: str) -> bool:
        return bool(claim_config_here(self._cwd)) and has_worktree(story, self._cwd)

    def take_back(self, story: str) -> TakenBack:
        cwd = self._cwd
        config = claim_config_here(cwd) or {}
        path = worktree_of(story, cwd)
        fetch_remote(cwd, config["remote"])
        main = remote_main(config["remote"], claim_target(cwd))
        spec_rel = os.path.relpath(place("spec") if os.path.isabs(place("spec")) else os.path.join(cwd, place("spec")),
                                   cwd)
        changed = [p for p in git(path, "diff", "--name-only", f"{main}...HEAD", "--", spec_rel)[1].splitlines()
                   if p.endswith(("scenarios.md", "journeys.md"))]
        for rel in changed:
            if git(path, "cat-file", "-e", f"{main}:{rel}")[0] == 0:
                git(path, "checkout", main, "--", rel)
            else:
                git(path, "rm", "--quiet", "--", rel)
        story_rel = os.path.relpath(find_story(self._epics, story), factory_home() or cwd)
        before = os.path.join(evidence_dir(self._runs, story), "published-status")
        status = read_text(before).strip() if os.path.isfile(before) else "approved"
        write_story_fields(os.path.join(path, story_rel), status=status or "approved", delivered=None,
                           delivered_by=None)
        git(path, "add", "-A", "--", *(changed + [story_rel]))
        git(path, *(["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
                    if not git(path, "config", "user.email")[1].strip() else []),
            "commit", "--no-verify", "--quiet", "-m", f"wip({story}): before it is delivered again")
        with contextlib.suppress(OSError):
            os.remove(os.path.join(evidence_dir(self._runs, story), PUBLISHED))
        return TakenBack(tuple(changed), main)
