"""When a claim on a story holds, collides, goes or is orphaned, and which story id is free (WP-93)."""

from __future__ import annotations

import re
import typing

from ....building_blocks import DomainService
from ..model.claim import ClaimedFor, Fate, IdPrefix, Meeting, Worker
from ..model.stage_story import Presence
from ..model.story import StoryId, StoryStatus


class ClaimRules(DomainService):
    """The claims of several factories on one backlog."""

    @staticmethod
    def meets(holder: Worker, me: Worker, claimed: ClaimedFor, story: ClaimedFor) -> Meeting:
        """An own claim holds; the same id claimed for another epic or title — where the claim names them — is a
        collision; otherwise another factory runs the story."""
        if holder == me:
            return Meeting.OWN
        if (claimed.epic.value and claimed.epic != story.epic) \
                or (claimed.title.value and claimed.title != story.title):
            return Meeting.COLLISION
        return Meeting.OTHERS

    @staticmethod
    def fate(on_main: typing.Optional[StoryStatus], published: Presence, branch: Presence) -> Fate:
        """A claim whose story is delivered on the remote main line goes; one whose story the main line does not
        have — and that no published mark or local story branch says is on its way — is an orphan."""
        if on_main is StoryStatus.DELIVERED:
            return Fate.RELEASED
        if on_main is None and published is Presence.ABSENT and branch is Presence.ABSENT:
            return Fate.ORPHAN
        return Fate.HOLDS

    @staticmethod
    def releases(holder: Worker, me: Worker, force: Presence) -> Presence:
        """A factory releases its own claim; another's only with force."""
        return Presence.PRESENT if holder == me or force is Presence.PRESENT else Presence.ABSENT

    @staticmethod
    def next_id(prefix: IdPrefix, used: typing.AbstractSet[StoryId]) -> StoryId:
        """The next `<prefix>-<n>` nobody uses — a delivered story's id included, which never comes free again —
        zero-padded to the widest number in use, two digits at least where none is."""
        pattern = re.compile(rf"^{re.escape(prefix.value)}-(\d+)$")
        digits = [m.group(1) for m in (pattern.match(story.value) for story in used) if m]
        width = max((len(d) for d in digits), default=2)
        return StoryId(f"{prefix.value}-{str(max((int(d) for d in digits), default=0) + 1).zfill(width)}")
