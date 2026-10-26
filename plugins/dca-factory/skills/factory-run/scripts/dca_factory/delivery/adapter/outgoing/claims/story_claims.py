"""The remote's story claims, as a command beside a run asks them."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from ....application.shared.story_claims import Claim, ClaimHeld, ClaimOutcome
from ....domain.model.story import StoryId
from ..git.repository import git
from ..files.run_marks import story_title
from ..files.story_layout import epic_folder, find_story
from .remote_claims import cached_claims, claim_config_here, claim_story, free_id, refresh_claims, release_claim

#: a claim's exit codes, as the runner reads them
CLAIM_CODES = {0: Claim.OWN, 3: Claim.ELSEWHERE, 4: Claim.NEEDS_PERSON}


def claim_target(cwd: str) -> str:
    """The branch the main checkout is on — the remote's branch of that name is the shared main line."""
    return git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip() or "main"


class RemoteStoryClaims:
    """The claims on the remote the profile names (`claim_remote:`), fetched fresh into the run folder <runs>; the
    stories under <epics>."""

    def __init__(self, cwd: str, runs: str, epics: str = "") -> None:
        self._cwd = cwd
        self._runs = runs
        self._epics = epics

    def held_elsewhere(self, story: StoryId) -> typing.Optional[ClaimHeld]:
        config = claim_config_here(self._cwd)
        if not config:
            return None
        refresh_claims(self._cwd, self._runs, config, claim_target(self._cwd), say=lambda _line: None)
        held = cached_claims(self._runs).get(story.value)
        if not held or held["own"]:
            return None
        return ClaimHeld(str(held["who"]), str(held["host"]), str(held["since"]))

    def claim(self, story: StoryId) -> ClaimOutcome:
        config = claim_config_here(self._cwd)
        if not config:
            return ClaimOutcome(Claim.NO_REMOTE, None, ())
        path = find_story(self._epics, story.value)
        front, body = read_front_matter(path)
        epic = str(front.get("epic") or os.path.basename(epic_folder(path))).strip()
        said: typing.List[str] = []
        code = claim_story(self._cwd, self._runs, config, claim_target(self._cwd), story.value, epic,
                           story_title(front, body) or story.value, say=lambda line: said.append(str(line)))
        claim = CLAIM_CODES.get(code, Claim.NEEDS_PERSON)
        held = None
        if claim is Claim.ELSEWHERE:
            found = cached_claims(self._runs).get(story.value, {})
            held = ClaimHeld(str(found.get("who", "?")), str(found.get("host", "?")), str(found.get("since", "?")))
        return ClaimOutcome(claim, held, tuple(said))

    def release(self, story: StoryId, force: bool) -> int:
        config = claim_config_here(self._cwd)
        if not config:
            print("release: the profile names no `claim_remote:` — there is no claim to release")
            return 1
        return release_claim(self._cwd, self._runs, config, story.value, force)

    def refresh(self) -> int:
        config = claim_config_here(self._cwd)
        return refresh_claims(self._cwd, self._runs, config, claim_target(self._cwd)) if config else 0

    def free_id(self, prefix: str) -> str:
        return free_id(self._cwd, self._epics, claim_config_here(self._cwd), claim_target(self._cwd), prefix)
