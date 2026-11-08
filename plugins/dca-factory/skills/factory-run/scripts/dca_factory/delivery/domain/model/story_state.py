"""Where a story stands in the schedule, and the facts of its run that say so."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .story_words import Detail as Detail, StatusWord as StatusWord
from .decision_record import RecordId
from .stage import StageName
from .story import StoryId
from .verdict import CheckName, Finding, Said

#: The schedule's states of a story that can run now: not started, begun, or stopped where it can continue.
RUNNABLE = ("ready", "in-progress", "resumable")

#: Rounds of judge and build a story may take before it stops as not converging.
MAX_ROUNDS = 3

ENVIRONMENT = "gate:fail environment"
FAILED, CLOSING = "gate:fail ", "gate:fail story "


class Judged(enum.Enum):
    """What the judge's verdict means for the run."""

    PASS = "pass"                       # on to the document stage
    AGAIN = "changes-requested"         # a round back to the stage the judge names
    CONFLICT = "story-conflict"         # the story or the plan is wrong: a person decides
    MISSING = "missing"                 # no `verdict:` line: the judge stage is not finished
    UNKNOWN = "unknown"                 # a word that is none of the three

    def adopt_finding(self) -> Finding:
        """A fresh judge confirms that each mapped test asserts its scenario before the story counts as adopted."""
        if self is not Judged.PASS:
            return CheckName("adopt-judged").fail(Said("judge.md carries no `verdict: pass` — a fresh judge confirms "
                                                       "that each mapped test asserts its scenario before the story "
                                                       "counts as adopted"))
        return CheckName("adopt-judged").ok(Said("the judge confirmed that the tests prove the scenarios"))


class Refusal(enum.Enum):
    """What the integrate gate refused the story for on the main line."""

    MOVED = "moved"             # nothing but the main line moving on meanwhile
    MAIN_TESTS = "main-tests"   # the resolution dropped what the main line added to a test
    CHECKOUT = "checkout"       # the main checkout could not take the story


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


class Standing(Value):
    """A story's state, the stage it runs from (None where it runs from none), and why."""

    state: StateName
    start: typing.Optional[StageName]
    detail: Detail

    @classmethod
    def twin(cls, story: StoryId, others: typing.Sequence[Detail]) -> typing.Optional[Standing]:
        """Two stories under one id would share a run folder and a row: each stops, naming where the others are."""
        if not others:
            return None
        return cls(StateName.STOPPED, None, Detail(
            f"id {story.value!r} is not unique — also {', '.join(o.value for o in others)}; give one of them another"))


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


class StoryMarks(Value):
    """The marks read before a story's run: in its evidence folder (a stage changed it, it is published), and the
    claim another factory holds on it."""

    marks: typing.FrozenSet[Mark]
    claimant: typing.Optional[Claimant]


class HandOverText(Value):
    """A stage's file of the story's current pass, as written."""

    value: str


class HandOverFacts(Value):
    """A current stage file: its text, its `verdict:`, and the records its `## needs-human` names (None without
    one)."""

    text: HandOverText
    verdict: Judged
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


class GateReport(Value):
    """The text of a gate's refusal."""

    value: str

    def environment(self) -> typing.Optional[Detail]:
        """A refusal whose cause is the machine, not the story — no stage can put a tool on the PATH, so it counts no
        round: its reason; None for a refusal of the story."""
        lines = self.value.splitlines()
        if not any(line.startswith(ENVIRONMENT) for line in lines):
            return None
        return Detail(next((line[len(ENVIRONMENT + " — "):] for line in lines
                            if line.startswith(ENVIRONMENT + " — ")), ""))

    def integration(self) -> typing.FrozenSet[Refusal]:
        """What the checks that failed on the main line say — not the report's closing `gate:fail story` line: only
        that the main line moved on, or that a test of the main line lost its side, or that the checkout could not
        take the story; empty for a refusal of the story itself."""
        fails = [line for line in self.value.splitlines() if line.startswith(FAILED) and not line.startswith(CLOSING)]
        if fails and all(line.startswith(FAILED + Refusal.MOVED.value) for line in fails):
            return frozenset((Refusal.MOVED,))
        return frozenset(refusal for refusal in (Refusal.MAIN_TESTS, Refusal.CHECKOUT)
                         if any(line.startswith(FAILED + refusal.value) for line in fails))

    def refused_checks(self) -> typing.Tuple[CheckName, ...]:
        """The checks a gate's report says failed, each once, in its order — not its closing `gate:fail story` line."""
        names: typing.List[CheckName] = []
        for line in self.value.splitlines():
            if line.startswith(FAILED) and not line.startswith(CLOSING):
                name = CheckName(line[len(FAILED):].split(" ", 1)[0])
                if name not in names:
                    names.append(name)
        return tuple(names)


class Rounds(Value):
    """How many rounds of judge and build the story took."""

    value: int

    def converged(self) -> typing.Optional[Detail]:
        """Where the rounds did not converge, why — None while another round may run."""
        if self.value >= MAX_ROUNDS:
            return Detail(f"{MAX_ROUNDS} rounds did not converge")
        return None


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
    """What the run of a released story left: the current pass's stage files, why its decision records could not be
    read (the records themselves are aggregates, read on their own), the marks, the refusals, the rounds and the
    acceptance."""

    hand_overs: typing.Mapping[StageName, HandOverFacts]
    unreadable: typing.Optional[Detail]
    marks: typing.FrozenSet[Mark]
    rounds: Rounds
    #: the stages whose gate refused, in the run order, and the stage files on disk — current or an earlier pass's
    refused: typing.Tuple[StageName, ...]
    on_disk: typing.FrozenSet[StageName]
    integrate_report: typing.Optional[GateReport]
    document_report: typing.Optional[GateReport]
    acceptance: typing.Optional[Acceptance]
