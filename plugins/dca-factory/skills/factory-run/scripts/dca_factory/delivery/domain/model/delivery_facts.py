"""What a delivery rests on: what its stages changed, its commit and pass, its documents and reviews, its merge."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .decision_record import RecordId
from .plan_facts import HandOverName, PlannedDigest
from .story_state import Detail, Judged
from .story_words import Count, Place, Presence


class Unobserved(enum.Enum):
    """Why a stage's changes cannot be held to its list: the stage is still open, no record was taken, or the
    record says why it saw nothing."""

    STAGE_OPEN = "stage open"
    NO_RECORD = "no record"
    NOT_OBSERVED = "not observed"


class StageChanges(Value):
    """What a stage changed and what its hand-overs list: the files changed, the hand-overs read, the files they
    list — None where none has a list —, and the changed tests that are the version the test stage saw red again."""

    unobserved: typing.Optional[Unobserved]
    reason: Detail
    changed: typing.Tuple[Place, ...]
    hand_overs: typing.Tuple[HandOverName, ...]
    listed: typing.Optional[typing.FrozenSet[Place]]
    restored: typing.FrozenSet[Place]


class StoryCommit(Value):
    """The story's commit against the test files its mapping and its spec name: its short id, how many files, and
    the ones it lacks or holds otherwise than the worktree."""

    head: Detail
    files: Count
    missing: typing.Tuple[Detail, ...]


class PassGap(Value):
    """A stage of this pass without its hand-over: missing, or written for an earlier pass."""

    hand_over: HandOverName
    earlier: Presence


class StoryPass(Value):
    """What a delivery rests on: the stages of this pass that did not write their file after the one before, the
    judge's verdict, and the story against the one planned."""

    gaps: typing.Tuple[PassGap, ...]
    verdict: Judged
    planned: PlannedDigest


class DocumentFacts(Value):
    """What the document stage wrote, read for what can be checked: why it cannot be read, whether it stopped with
    a question, how many documents it says it updated, the paths it names that do not resolve, its rows that say
    nothing of how they were checked."""

    place: Place
    unreadable: typing.Optional[Detail]
    asks: Presence
    files: Count
    missing: typing.Tuple[Detail, ...]
    unsourced: typing.Tuple[Detail, ...]


class ReviewFacts(Value):
    """The review perspectives: the ones with a report, without a file, with a file that is no report — and the
    perspectives the judge's confirmed findings name that the profile does not know (`unknown`)."""

    read: typing.Tuple[Detail, ...]
    missing: typing.Tuple[Detail, ...]
    malformed: typing.Tuple[Detail, ...]
    unknown: typing.Tuple[Detail, ...] = ()


class PipelineFacts(Value):
    """The installed pipeline's folder, and the files of it a stage changed — None where no stage left a record."""

    folder: Place
    touched: typing.Optional[typing.Tuple[Place, ...]]


class Integration(Value):
    """The story's branch against the main line: whether the gate runs in the story's worktree (and the variable
    that names the main checkout), whether its target is recorded, the target, the paths left unmerged, the story's
    files with a conflict marker left, and whether the target moved on since the merge."""

    worktree: Presence
    home_variable: Detail
    recorded: Presence
    target: Detail
    unmerged: typing.Tuple[Place, ...]
    marked: typing.Tuple[Place, ...]
    moved: Presence


class MainTestLines(Value):
    """A test file and lines of it: the main line's lines a merge rewrote, or lost."""

    place: Place
    lines: typing.Tuple[Detail, ...]


class MainTests(Value):
    """The main line's side of the tests a merge met: the lines rewritten to a name the story re-signed, the files
    an answered integrate decision settles (with its ids), the lines the resolution lost, and the target."""

    adapted: typing.Tuple[MainTestLines, ...]
    waived: typing.Tuple[typing.Tuple[Place, typing.Tuple[RecordId, ...]], ...]
    lost: Detail
    target: Detail
