"""The schedule: every story in its order, what each waits for, and which may start now."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .epic import EpicId
from .stage import StageName
from .story import StoryId
from .story_state import Detail, Standing


class ContextName(Value):
    """The bounded context a story changes, as its `context:` names it — "" where it names none."""

    value: str


class Liveness(enum.Enum):
    """A stage begun and not ended: still within the time a stage may take, or silent past it."""

    ALIVE = "alive"
    SILENT = "silent"


class Running(Value):
    """A stage — or the runner's own step — begun and not ended, since when, and whether it still counts as
    running."""

    stage: StageName
    since: Detail
    liveness: Liveness


class Holding(enum.Enum):
    """What a story holds: unfinished code in the checkout, or its worktree."""

    CHECKOUT = "checkout"
    WORKTREE = "worktree"


class Entry(Value):
    """One story as the schedule reads it."""

    story: StoryId
    standing: Standing
    depends_on: typing.Tuple[StoryId, ...]
    epic: EpicId
    context: ContextName
    holds: typing.FrozenSet[Holding]
    running: typing.Optional[Running]


class EpicGraph(Value):
    """The epics' `depends_on:`, their order, and those on a cycle."""

    needs: typing.Mapping[EpicId, typing.Tuple[EpicId, ...]]
    ranked: typing.Tuple[EpicId, ...]
    cycle: typing.FrozenSet[EpicId]


class Slots(Value):
    """How many stories a runner runs at once, each in its worktree."""

    value: int


class Wait(enum.Enum):
    """Whether something waits that a later look may change: a person's answer, a running stage."""

    YES = "yes"
    NO = "no"


class Schedule(Value):
    """Every story's standing in the order, the stories that start now, and why none does where none does."""

    order: typing.Tuple[StoryId, ...]
    standings: typing.Mapping[StoryId, Standing]
    starts: typing.Tuple[StoryId, ...]
    reason: Detail
    wait: Wait


