"""A story's published branch in its worktree, its delivery taken back with git."""

from __future__ import annotations

import contextlib
import os

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home, place
from ....application.shared.published_branches import TakenBack
from ..claims.remote_claims import claim_config_here, fetch_remote, PUBLISHED, remote_main
from ..claims.story_claims import claim_target
from ..files.story_files import StoryFiles, status_of
from ..files.story_layout import find_story
from ....application.shared.story_repository import StoryRepository
from ....domain.model.story import StoryId, StoryStatus
from .repository import git
from .worktrees import has_worktree, worktree_of
from ....application.shared.published_branches import PublishedBranches


class PublishedBranchFiles(PublishedBranches):
    """The published branches of the checkout <cwd>, the stories under <epics>, the run folder <runs>."""

    def __init__(self, cwd: str, runs: str, epics: str) -> None:
        self._cwd = cwd
        self._runs = runs
        self._epics = epics

    def published(self, story: StoryId) -> bool:
        return bool(claim_config_here(self._cwd)) and has_worktree(story.value, self._cwd)

    def published_over(self, story: StoryId) -> StoryStatus:
        before = os.path.join(evidence_dir(self._runs, story.value), "published-status")
        word = read_text(before).strip() if os.path.isfile(before) else ""
        return status_of(word) if word else StoryStatus.APPROVED

    def stories(self, story: StoryId) -> StoryRepository:
        path = worktree_of(story.value, self._cwd)
        home = factory_home() or self._cwd
        return StoryFiles(path, os.path.join(path, os.path.relpath(os.path.abspath(self._epics), home)))

    def set_back_spec(self, story: StoryId) -> TakenBack:
        cwd = self._cwd
        config = claim_config_here(cwd) or {}
        path = worktree_of(story.value, cwd)
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
        return TakenBack(tuple(changed), main)

    def commit_taken_back(self, story: StoryId, taken: TakenBack) -> None:
        path = worktree_of(story.value, self._cwd)
        story_rel = os.path.relpath(find_story(self._epics, story.value), factory_home() or self._cwd)
        git(path, "add", "-A", "--", *(list(taken.spec_files) + [story_rel]))
        git(path, *(["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
                    if not git(path, "config", "user.email")[1].strip() else []),
            "commit", "--no-verify", "--quiet", "-m", f"wip({story.value}): before it is delivered again")
        with contextlib.suppress(OSError):
            os.remove(os.path.join(evidence_dir(self._runs, story.value), PUBLISHED))
