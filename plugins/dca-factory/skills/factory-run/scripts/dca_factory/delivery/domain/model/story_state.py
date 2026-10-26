"""Where a story stands in the schedule, and the facts of its run that say so."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .decision_record import DecisionState, RecordId, RecordKind
from .stage import StageName, StoryKind
from .story import StoryId

#: The schedule's states of a story that can run now: not started, begun, or stopped where it can continue.
RUNNABLE = ("ready", "in-progress", "resumable")

#: Rounds of judge and build a story may take before it stops as not converging.
MAX_ROUNDS = 3


class StateName(enum.Enum):
    """A story's state: what the schedule shows and the runner acts on."""

    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    IN_PROGRESS = "in-progress"
    RESUMABLE = "resumable"
    WAITING = "waiting"
    STOPPED = "stopped"
    UNRELEASED = "unreleased"
    PUBLISHED = "published"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    SUPERSEDED = "superseded"


#: A story at its end: delivered, or replaced by another — it holds nothing and waits for nothing.
ENDED = frozenset((StateName.DELIVERED, StateName.SUPERSEDED))
ENDED_WORDS = frozenset(state.value for state in ENDED)


class Detail(Value):
    """Why a story stands where it stands, for a person — "" where nothing needs saying."""

    value: str


class Standing(Value):
    """A story's state, the stage it runs from (None where it runs from none), and why."""

    state: StateName
    start: typing.Optional[StageName]
    detail: Detail


class StatusWord(Value):
    """A story's `status:` as it is written, lower case — `approved`, `adopted`, `draft`, or a word nobody knows."""

    value: str


class Claimant(Value):
    """Who claimed a story in another factory and since when, as the claim names it: `<who> (<host>) since <at>`."""

    value: str


class Mark(enum.Enum):
    """What the run of a story left that decides where it stands:

    - OWNED_CHANGED    the story or an answer changed under a stage;
    - PUBLISHED        this factory published the story as its branch;
    - CHANGED_SINCE_PLAN  the story is not what its plan was made of;
    - PLAN_REFUSED     the plan gate refused the story;
    - REPAIRED         the story or its epic changed since that refusal;
    - INTEGRATE_REFUSED  the integrate gate refused the story, and no build wrote since;
    - WORKTREE         the story has its worktree;
    - ADOPT_PASSED     the adopt gate passed after the judge's file was written;
    - DOCUMENT_PASSED  the document gate passed after its file was written."""

    OWNED_CHANGED = "owned-changed"
    PUBLISHED = "published"
    CHANGED_SINCE_PLAN = "changed-since-plan"
    PLAN_REFUSED = "plan-refused"
    REPAIRED = "repaired"
    INTEGRATE_REFUSED = "integrate-refused"
    WORKTREE = "worktree"
    ADOPT_PASSED = "adopt-passed"
    DOCUMENT_PASSED = "document-passed"


class StoryFront(Value):
    """What a story says about itself, and the marks read before its run: enough for every story not running."""

    story: StoryId
    status: StatusWord
    kind: StoryKind
    #: who claims the delivery where the story is delivered — "" for the gate, `hand:<who>` for a person; None where
    #: it is not delivered
    delivered_by: typing.Optional[Detail]
    marks: typing.FrozenSet[Mark]
    claimant: typing.Optional[Claimant]


class HandOverText(Value):
    """A stage's file of the story's current pass, as written."""

    value: str


class VerdictWord(Value):
    """The judge's `verdict:` — `pass`, `changes-requested`, `story-conflict` — or "" where it wrote none."""

    value: str


class HandOverFacts(Value):
    """A current stage file: its text, its `verdict:`, and the records its `## needs-human` names (None without
    one)."""

    text: HandOverText
    verdict: VerdictWord
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


class RecordFacts(Value):
    """A decision record of the story: its id, its state, the stage its answer resumes at, and its kind."""

    id: RecordId
    state: DecisionState
    resumes: typing.Optional[StageName]
    kind: RecordKind


class GateReport(Value):
    """The text of a gate's refusal."""

    value: str


class Rounds(Value):
    """How many rounds of judge and build the story took."""

    value: int


class AcceptanceVerdict(enum.Enum):
    """Where the story's acceptance stands for the story as it is now."""

    ASK = "ask"
    OPEN = "open"
    ACCEPTED = "accepted"
    CORRECTION = "correction"


class Acceptance(Value):
    verdict: AcceptanceVerdict
    record: typing.Optional[RecordId]


class RunFacts(Value):
    """What the run of a released story left: the current pass's stage files, the records (or why they could not
    be read), the marks, the refusals, the rounds and the acceptance."""

    hand_overs: typing.Mapping[StageName, HandOverFacts]
    records: typing.Tuple[RecordFacts, ...]
    unreadable: typing.Optional[Detail]
    marks: typing.FrozenSet[Mark]
    rounds: Rounds
    #: the stages whose gate refused, in the run order, and the stage files on disk — current or an earlier pass's
    refused: typing.Tuple[StageName, ...]
    on_disk: typing.FrozenSet[StageName]
    integrate_report: typing.Optional[GateReport]
    document_report: typing.Optional[GateReport]
    acceptance: typing.Optional[Acceptance]
