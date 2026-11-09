"""A claim on a story across factories (WP-93): the story's branch on a shared remote, as a lock."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Value
from .epic import EpicId
from .story_words import Presence
from .story import StoryId, StoryStatus


class Worker(Value):
    """A factory that claims: the person and the host it runs on, as one name."""

    value: str


class ClaimTitle(Value):
    """A story's title as a claim names it — "" where an older claim named none."""

    value: str


class ClaimedFor(Value):
    """What a claim says it is for: the story's epic and title, each "" where the claim named none."""

    epic: EpicId
    title: ClaimTitle


class IdPrefix(Value):
    """What a project's story ids begin with, before `-<number>` — `STORY`."""

    value: str

    def next_id(self, used: typing.AbstractSet[StoryId]) -> StoryId:
        """The next `<prefix>-<n>` nobody uses — a delivered story's id included, which never comes free again —
        zero-padded to the widest number in use, two digits at least where none is."""
        pattern = re.compile(rf"^{re.escape(self.value)}-(\d+)$")
        digits = [m.group(1) for m in (pattern.match(story.value) for story in used) if m]
        width = max((len(d) for d in digits), default=2)
        return StoryId(f"{self.value}-{str(max((int(d) for d in digits), default=0) + 1).zfill(width)}")


class Meeting(enum.Enum):
    """What a factory finds where it claims a story another claim names already."""

    #: this factory's own claim
    OWN = "own"
    #: the same id for another story — a person gives one of them another id
    COLLISION = "collision"
    #: another factory runs this story
    OTHERS = "others"


class Fate(enum.Enum):
    """What becomes of a claim after a fetch of the remote."""

    HOLDS = "holds"
    #: its story is delivered on the remote main line: any factory that sees it releases it
    RELEASED = "released"
    #: the remote main line has no such story, and nothing here says it is coming: a person releases it
    ORPHAN = "orphan"



class ClaimTrace(Value):
    """What a fetch of the remote found of a claimed story: its status on the remote main line (None where the main
    line has no such story), whether this factory published it, whether a local story branch carries it."""

    on_main: typing.Optional[StoryStatus]
    published: Presence
    branch: Presence

    def fate(self) -> Fate:
        """A claim whose story is delivered on the remote main line goes; one whose story the main line does not
        have — and that no published mark or local story branch says is on its way — is an orphan."""
        if self.on_main is StoryStatus.DELIVERED:
            return Fate.RELEASED
        if self.on_main is None and self.published is Presence.ABSENT and self.branch is Presence.ABSENT:
            return Fate.ORPHAN
        return Fate.HOLDS


class Claim(Value):
    """A claim on a story: the factory that holds it and what it says it is for."""

    holder: Worker
    claimed: ClaimedFor

    def meets(self, me: Worker, story: ClaimedFor) -> Meeting:
        """An own claim holds; the same id claimed for another epic or title — where the claim names them — is a
        collision; otherwise another factory runs the story."""
        if self.holder == me:
            return Meeting.OWN
        if (self.claimed.epic.value and self.claimed.epic != story.epic) \
                or (self.claimed.title.value and self.claimed.title != story.title):
            return Meeting.COLLISION
        return Meeting.OTHERS

    def released_by(self, me: Worker, force: Presence) -> Presence:
        """A factory releases its own claim; another's only with force."""
        return Presence.PRESENT if self.holder == me or force is Presence.PRESENT else Presence.ABSENT
