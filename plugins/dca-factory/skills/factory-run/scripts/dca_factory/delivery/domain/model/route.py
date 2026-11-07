"""A story's route through its stages, as the workflow decides it: how the run takes each stage, and why a kind
skips one."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .stage import StageName, StoryKind
from .story_state import Detail

JUDGE = StageName("judge")


class Move(enum.Enum):
    """How the run takes a stage of the route."""

    SKIP = "skip"           # the story's kind does not run it
    STAGE = "stage"         # a process of its own
    BUILDER = "builder"     # the shared builder starts here and carries the rest of its window
    CARRIED = "carried"     # carried by the shared builder started before it
    VERIFIER = "verifier"   # the shared verifier carries the rest of the route


class Around(enum.Enum):
    """What the run does around a stage."""

    PAUSE = "pause"             # the requests about other stories are worked before it
    GATE_BEFORE = "gate-before"  # its gate runs before it
    REVIEWS = "reviews"         # the reviews run before it, one process per perspective
    GATE_AFTER = "gate-after"   # its gate runs once its file is written
    VERDICT = "verdict"         # the judge's verdict decides what comes after it


class RouteStep(Value):
    """One stage of the route and how the run takes it; `skipped` says why a kind does not run it."""

    stage: StageName
    move: Move
    around: typing.FrozenSet[Around]
    skipped: typing.Optional[Detail] = None


#: Why a kind runs no stage of the builder: what a person reads beside the skipped stage.
SKIP_REASONS = {StoryKind.JOURNEY: "a journey builds nothing", StoryKind.ADOPT: "an adopted story is not built",
                StoryKind.TASK: "a task has no criterion to test — the existing suite is its evidence"}
#: The kinds that change the code, so the review perspectives have a change to read before the judge; an adoption
#: changes nothing.
REVIEWED_KINDS = frozenset((StoryKind.STORY, StoryKind.JOURNEY, StoryKind.TASK))
