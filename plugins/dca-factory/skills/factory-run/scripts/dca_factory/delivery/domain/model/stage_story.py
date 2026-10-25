"""The story as a stage's gate reads it, and the facts its checks are handed."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import Value
from .decision_record import DecisionState, RecordId, RecordKind
from .epic import EpicId
from .schedule import ContextName
from .stage import StageName, StoryKind
from .story import DeliveredOn, StoryId
from .story_state import Detail, HandOverText, Rounds, StatusWord


@dataclasses.dataclass(frozen=True)
class Place(Value):
    """A file as the gate names it — where a person finds what a finding speaks of."""

    value: str


@dataclasses.dataclass(frozen=True)
class Count(Value):
    value: int


@dataclasses.dataclass(frozen=True)
class ScenarioKey(Value):
    """A criterion's key — the name the test stage binds."""

    value: str


@dataclasses.dataclass(frozen=True)
class RowId(Value):
    """A finding row a task closes: `<story>#<n>`, or `<name>#<n>` of a project finding file."""

    value: str


@dataclasses.dataclass(frozen=True)
class RowState(Value):
    """Where a finding row stands: `open`, or what closed it."""

    value: str


@dataclasses.dataclass(frozen=True)
class EventName(Value):
    """An outcome event, as a story's `publishes:` names it."""

    value: str


@dataclasses.dataclass(frozen=True)
class StageStory(Value):
    """One story under a gate: what its front matter and its criteria say."""

    story: StoryId
    place: Place
    epic: typing.Optional[EpicId]
    context: ContextName
    kind: StoryKind
    status: StatusWord
    delivered_on: DeliveredOn
    criteria: typing.Tuple[ScenarioKey, ...]
    happy_paths: typing.Tuple[ScenarioKey, ...]
    depends_on: typing.Tuple[StoryId, ...]
    closes: typing.Tuple[RowId, ...]
    publishes: typing.Tuple[EventName, ...]
    #: what each scenario says is observed: its `Then` and every `And` or `But` after it
    clauses: typing.Tuple[ScenarioClauses, ...] = ()
    #: the lines of its `## Changed expectations` a person wrote
    changed_expectations: Count = Count(0)


@dataclasses.dataclass(frozen=True)
class ContractNumber(Value):
    """A gate contract: what the gate reads and writes, raised when that changes incompatibly."""

    value: int


@dataclasses.dataclass(frozen=True)
class GateRelease(Value):
    """The gate that checks: the contract it implements and its version."""

    contract: ContractNumber
    version: Detail


@dataclasses.dataclass(frozen=True)
class ProfileKey(Value):
    value: str


@dataclasses.dataclass(frozen=True)
class ProfileText(Value):
    """A profile value, as written."""

    value: str


@dataclasses.dataclass(frozen=True)
class UnknownKey(Value):
    """A profile key nobody reads, and the nearest key that is read."""

    key: ProfileKey
    near: typing.Optional[ProfileKey]


@dataclasses.dataclass(frozen=True)
class ModelKey(Value):
    """A `model…` key of the profile and its value."""

    key: ProfileKey
    value_written: ProfileText


@dataclasses.dataclass(frozen=True)
class RoundsRecord(Value):
    """The rounds a story ran without converging, as its counter holds them — None where the counter is no number."""

    place: Place
    rounds: typing.Optional[Rounds]


@dataclasses.dataclass(frozen=True)
class OwnedPart(Value):
    """Something of the person's a stage may not change: the story, an answer."""

    value: str


@dataclasses.dataclass(frozen=True)
class OwnedFacts(Value):
    """What a stage changed of the person's: the parts a past window marked, and those changed while this one runs —
    None where nothing records what they were."""

    marked: typing.Tuple[OwnedPart, ...]
    changed: typing.Optional[typing.Tuple[OwnedPart, ...]]


@dataclasses.dataclass(frozen=True)
class ContextMapFacts(Value):
    """The context map a story's context is looked up on: the designed map's file where the profile names one that
    is not there, the map found, and the names it gives."""

    domain_missing: typing.Optional[Place]
    map: typing.Optional[Place]
    names: typing.FrozenSet[ContextName]


@dataclasses.dataclass(frozen=True)
class ByteSize(Value):
    value: int


@dataclasses.dataclass(frozen=True)
class InstructionFile(Value):
    """The project's instruction file a tool loads first, and its size."""

    place: Place
    size: ByteSize


@dataclasses.dataclass(frozen=True)
class EpicField(Value):
    """A mandatory field of an epic's front matter."""

    value: str


@dataclasses.dataclass(frozen=True)
class Metric(Value):
    """An epic's `metric:` — the outcome event that measures it."""

    value: str


@dataclasses.dataclass(frozen=True)
class EpicFacts(Value):
    """A story's epic: its file and name, the mandatory fields it lacks, the discovery report it names and lacks, why
    its dependencies do not hold, and its metric."""

    place: Place
    name: EpicId
    missing: typing.Tuple[EpicField, ...]
    discovery_missing: typing.Optional[ProfileText]
    dependency_problem: typing.Optional[Detail]
    metric: Metric


@dataclasses.dataclass(frozen=True)
class AnswerField(Value):
    """A line a confirmed answer carries: `answer:`, `by:`, `at:`."""

    value: str


@dataclasses.dataclass(frozen=True)
class DecisionFacts(Value):
    """One decision record of the story, as its gate reads it: where it stands, the stage that asked it (open or a
    draft) or applies its answer, its question, the answer and who gave it, the answer lines a draft lacks."""

    record: RecordId
    kind: RecordKind
    state: DecisionState
    stage: typing.Optional[StageName]
    question: Detail
    place: Place
    answer: Detail
    by: Detail
    missing: typing.Tuple[AnswerField, ...]


@dataclasses.dataclass(frozen=True)
class HandOverAsk(Value):
    """A stage's hand-over as the decisions check reads it: its text, and the records its `## needs-human` names —
    None where it escalates nothing, none where it escalates without naming one."""

    stage: StageName
    place: Place
    text: HandOverText
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


@dataclasses.dataclass(frozen=True)
class DecisionsFacts(Value):
    """The story's decision records under their store, and the stages' hand-overs."""

    store: Place
    records: typing.Tuple[DecisionFacts, ...]
    hand_overs: typing.Tuple[HandOverAsk, ...]


@dataclasses.dataclass(frozen=True)
class Selector(Value):
    """A test as the tests table names it: `<Class>#<method>`."""

    value: str


@dataclasses.dataclass(frozen=True)
class CommandKey(Value):
    """A profile key of a test command — `test`, `e2eTest`, `test.journey`."""

    value: str


class TitleFound(enum.Enum):
    """Whether an end-user test is reported under its scenario's title."""

    TITLED = "titled"
    UNTITLED = "untitled"


@dataclasses.dataclass(frozen=True)
class TitleCheck(Value):
    """An end-user test's scenario title, and whether the test is reported under it."""

    title: Detail
    found: TitleFound


@dataclasses.dataclass(frozen=True)
class MappedTest(Value):
    """One row of the tests table: the criterion, its test, the file it was found in, the command that runs that
    file, and — for an end-user test of a titled scenario — its title check."""

    key: ScenarioKey
    selector: Selector
    place: typing.Optional[Place]
    command: typing.Optional[CommandKey]
    title: typing.Optional[TitleCheck]


@dataclasses.dataclass(frozen=True)
class TestTable(Value):
    """The test stage's table: where it stands and the criteria its rows name, row by row."""

    place: Place
    keys: typing.Tuple[ScenarioKey, ...]
    tests: Count


@dataclasses.dataclass(frozen=True)
class TestLocation(Value):
    """Where a mapped test was looked for: the file it was found in by its shape, or the file named after its class
    that lacks the method, or neither."""

    key: ScenarioKey
    selector: Selector
    found: typing.Optional[Place]
    candidate: typing.Optional[Place]
    shape: Detail


@dataclasses.dataclass(frozen=True)
class PlanLevels(Value):
    """The levels the plan gave: the keys its skeleton left without one, the keys it gave `browser-only`, the keys
    it gave `integration (adapter: …)` — an incoming adapter's translation, tested against a stubbed input port by
    design."""

    unfinished: typing.Tuple[ScenarioKey, ...]
    browser_only: typing.FrozenSet[ScenarioKey]
    adapter: typing.FrozenSet[ScenarioKey]


@dataclasses.dataclass(frozen=True)
class HandOverSize(Value):
    """A hand-over and the bytes of it the stage wrote."""

    name: HandOverName
    size: ByteSize


@dataclasses.dataclass(frozen=True)
class HandOverName(Value):
    value: str


@dataclasses.dataclass(frozen=True)
class ElementName(Value):
    """A domain type the plan names — `Task`, `TaskTitle`."""

    value: str


@dataclasses.dataclass(frozen=True)
class Rule(Value):
    """One invariant of a domain type, as the plan words it — a guard included."""

    value: str


@dataclasses.dataclass(frozen=True)
class ElementRules(Value):
    """A domain type's line under the plan's `## Invariants`: its rules, none where it says why it has none."""

    element: ElementName
    rules: typing.Tuple[Rule, ...]


@dataclasses.dataclass(frozen=True)
class InvariantRow(Value):
    """A row of the tests' `gate:invariants` table: the type, the rule numbers it covers, and its unit test — the
    selector where one is written as `<Class>#<method>`, the text where it is not."""

    element: ElementName
    numbers: typing.Tuple[Count, ...]
    selector: typing.Optional[Selector]
    malformed: typing.Optional[Detail]


@dataclasses.dataclass(frozen=True)
class InvariantFacts(Value):
    """What the plan says of the domain types it changes, and the tests' table of their rules."""

    listed: Count
    elements: typing.Tuple[ElementName, ...]
    named: typing.Tuple[ElementRules, ...]
    rows: typing.Optional[typing.Tuple[InvariantRow, ...]]


@dataclasses.dataclass(frozen=True)
class Clause(Value):
    """An expectation of a scenario — its `Then` or an `And`/`But` after it — numbered from 1."""

    number: Count
    text: Detail


@dataclasses.dataclass(frozen=True)
class ScenarioClauses(Value):
    key: ScenarioKey
    clauses: typing.Tuple[Clause, ...]


@dataclasses.dataclass(frozen=True)
class ClauseRow(Value):
    """A row of the tests' `gate:clauses` table: the clause, the line that asserts it, the level it runs at."""

    key: ScenarioKey
    number: Count
    location: Detail
    level: Detail


class AssertionAt(enum.Enum):
    """What a line of a test file does: there is no such file, the statement asserts nothing, or it asserts."""

    NO_FILE = "no file"
    NOTHING = "nothing"
    ASSERTS = "asserts"


@dataclasses.dataclass(frozen=True)
class AssertionFact(Value):
    """A test file's line as an assertion: what the line does, and whether the file is one of the given tests."""

    state: AssertionAt
    among: Presence


@dataclasses.dataclass(frozen=True)
class PortName(Value):
    """A port type a test declares as a double."""

    value: str


class FileChange(enum.Enum):
    NEW = "new"
    REMOVED = "removed"


class Presence(enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"


@dataclasses.dataclass(frozen=True)
class PlannedFile(Value):
    """A file the plan's `## Files` says becomes new or is removed, and whether it is there after the build."""

    place: Place
    change: FileChange
    presence: Presence


class Unobserved(enum.Enum):
    """Why a stage's changes cannot be held to its list: the stage is still open, no record was taken, or the
    record says why it saw nothing."""

    STAGE_OPEN = "stage open"
    NO_RECORD = "no record"
    NOT_OBSERVED = "not observed"


@dataclasses.dataclass(frozen=True)
class StageChanges(Value):
    """What a stage changed and what its hand-overs list: the files changed, the hand-overs read, the files they
    list — None where none has a list —, and the changed tests that are the version the test stage saw red again."""

    unobserved: typing.Optional[Unobserved]
    reason: Detail
    changed: typing.Tuple[Place, ...]
    hand_overs: typing.Tuple[HandOverName, ...]
    listed: typing.Optional[typing.FrozenSet[Place]]
    restored: typing.FrozenSet[Place]


class TestChange(enum.Enum):
    """How a test that existed before the story differs now."""

    CHANGED = "changed"
    REMOVED = "removed"
    SWITCHED_OFF = "switched off"


@dataclasses.dataclass(frozen=True)
class ChangedTest(Value):
    place: Place
    how: TestChange


@dataclasses.dataclass(frozen=True)
class KeptTests(Value):
    """The tests that existed before the story, against their baseline: the ones that no longer expect what they
    did, the ones whose baseline git lost, the ones changed only around their assertions."""

    changed: typing.Tuple[ChangedTest, ...]
    lost: typing.Tuple[Place, ...]
    arranged: typing.Tuple[Place, ...]


@dataclasses.dataclass(frozen=True)
class DecidedRecord(Value):
    """An answered decision about tests: the stage that asked it, and its text."""

    record: RecordId
    stage: typing.Optional[StageName]
    text: Detail


@dataclasses.dataclass(frozen=True)
class PlannedTestChange(Value):
    """A row of the plan's `## Changed tests`: the test, and what the row cites."""

    place: Place
    cites: Detail


@dataclasses.dataclass(frozen=True)
class RedProof(Value):
    """The red ledger against the tests as they are: how many tests it names, how many without a file digest, the
    tests whose file changed since, and — at tidy — whether tidy reworked a test the red tree can prove again."""

    entries: Count
    unbound: Count
    moved: typing.Tuple[Detail, ...]
    reproof: Presence
