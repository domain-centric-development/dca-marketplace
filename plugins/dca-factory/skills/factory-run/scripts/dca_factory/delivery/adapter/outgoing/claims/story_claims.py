"""The remote's story claims, as a command beside a run asks them."""

from __future__ import annotations

import typing

from ....application.shared.story_claims import ClaimHeld
from ....domain.model.story import StoryId
from ..git.repository import git
from .remote_claims import cached_claims, claim_config_here, refresh_claims


def claim_target(cwd: str) -> str:
    """The branch the main checkout is on — the remote's branch of that name is the shared main line."""
    return git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip() or "main"


class RemoteStoryClaims:
    """The claims on the remote the profile names (`claim_remote:`), fetched fresh into the run folder <runs>."""

    def __init__(self, cwd: str, runs: str) -> None:
        self._cwd = cwd
        self._runs = runs

    def held_elsewhere(self, story: StoryId) -> typing.Optional[ClaimHeld]:
        config = claim_config_here(self._cwd)
        if not config:
            return None
        refresh_claims(self._cwd, self._runs, config, claim_target(self._cwd), say=lambda _line: None)
        held = cached_claims(self._runs).get(story.value)
        if not held or held["own"]:
            return None
        return ClaimHeld(str(held["who"]), str(held["host"]), str(held["since"]))
