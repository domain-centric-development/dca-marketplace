"""A claim on a story across factories (WP-93): the story's branch on a shared remote, as a lock."""

from __future__ import annotations

import enum

from ....building_blocks import Value
from .epic import EpicId


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
