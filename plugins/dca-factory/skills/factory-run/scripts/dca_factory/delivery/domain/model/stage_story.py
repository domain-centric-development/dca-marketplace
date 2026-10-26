"""The story as a stage's gate reads it, and the facts its checks are handed."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Value
from .decision_record import AnswerField, DecisionState, RecordId, RecordKind
from .epic import EpicId
from .schedule import ContextName
from .stage import StageName, StoryKind
from .story import DeliveredOn, StoryId
from .story_state import Detail, HandOverText, Rounds, StatusWord


class Place(Value):
    """A file as the gate names it — where a person finds what a finding speaks of."""

    value: str


class Count(Value):
    value: int


class ScenarioKey(Value):
    """A criterion's key — the name the test stage binds."""

    value: str


class RowId(Value):
    """A finding row a task closes: `<story>#<n>`, or `<name>#<n>` of a project finding file."""

    value: str


class RowState(Value):
    """Where a finding row stands: `open`, or what closed it."""

    value: str


#: A finding row nobody closed yet — the only one a task may close; its delivery sets the row to DONE_ROW.
OPEN_ROW = RowState("open")
DONE_ROW = RowState("done")


class FindingKey(Value):
    """What makes a kept finding the same as another: where it is (`file:line`) and the defect it names."""

    place: Place
    defect: Detail


class EventName(Value):
    """An outcome event, as a story's `publishes:` names it."""

    value: str


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
    #: the feature of its context it changes, as its `feature:` names it — "" where it names none
    feature: Detail = Detail("")


class ContractNumber(Value):
    """A gate contract: what the gate reads and writes, raised when that changes incompatibly."""

    value: int


class GateRelease(Value):
    """The gate that checks: the contract it implements and its version."""

    contract: ContractNumber
    version: Detail


class ProfileKey(Value):
    value: str


class ProfileText(Value):
    """A profile value, as written."""

    value: str


class UnknownKey(Value):
    """A profile key nobody reads, and the nearest key that is read."""

    key: ProfileKey
    near: typing.Optional[ProfileKey]


class ModelKey(Value):
    """A `model…` key of the profile and its value."""

    key: ProfileKey
    value_written: ProfileText


class RoundsRecord(Value):
    """The rounds a story ran without converging, as its counter holds them — None where the counter is no number."""

    place: Place
    rounds: typing.Optional[Rounds]


class OwnedPart(Value):
    """Something of the person's a stage may not change: the story, an answer."""

    value: str


class OwnedFacts(Value):
    """What a stage changed of the person's: the parts a past window marked, and those changed while this one runs —
    None where nothing records what they were."""

    marked: typing.Tuple[OwnedPart, ...]
    changed: typing.Optional[typing.Tuple[OwnedPart, ...]]


class ContextMapFacts(Value):
    """The context map a story's context is looked up on: the designed map's file where the profile names one that
    is not there, the map found, and the names it gives."""

    domain_missing: typing.Optional[Place]
    map: typing.Optional[Place]
    names: typing.FrozenSet[ContextName]


class ByteSize(Value):
    value: int


class InstructionFile(Value):
    """The project's instruction file a tool loads first, and its size."""

    place: Place
    size: ByteSize


class EpicField(Value):
    """A mandatory field of an epic's front matter."""

    value: str


class Metric(Value):
    """An epic's `metric:` — the outcome event that measures it."""

    value: str


class EpicFacts(Value):
    """A story's epic: its file and name, the mandatory fields it lacks, the discovery report it names and lacks, why
    its dependencies do not hold, and its metric — or why the story names no epic there is."""

    place: Place
    name: EpicId
    missing: typing.Tuple[EpicField, ...]
    discovery_missing: typing.Optional[ProfileText]
    dependency_problem: typing.Optional[Detail]
    metric: Metric
    unreadable: typing.Optional[Detail] = None


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


class HandOverAsk(Value):
    """A stage's hand-over as the decisions check reads it: its text, and the records its `## needs-human` names —
    None where it escalates nothing, none where it escalates without naming one."""

    stage: StageName
    place: Place
    text: HandOverText
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


class DecisionsFacts(Value):
    """The story's decision records under their store, and the stages' hand-overs — or why the store cannot be
    read."""

    store: Place
    records: typing.Tuple[DecisionFacts, ...]
    hand_overs: typing.Tuple[HandOverAsk, ...]
    unreadable: typing.Optional[Detail] = None


#: The form of a test's name in the tests table: the fully qualified class, then the test method.
SELECTOR_FORM = re.compile(r"^([\w.]+)#([\w]+)$")


class Selector(Value):
    """A test as the tests table names it: `<Class>#<method>`."""

    value: str


class CommandKey(Value):
    """A profile key of a test command — `test`, `e2eTest`, `test.journey`."""

    value: str


class TitleFound(enum.Enum):
    """Whether an end-user test is reported under its scenario's title."""

    TITLED = "titled"
    UNTITLED = "untitled"


class TitleCheck(Value):
    """An end-user test's scenario title, and whether the test is reported under it."""

    title: Detail
    found: TitleFound


class MappedTest(Value):
    """One row of the tests table: the criterion, its test, the file it was found in, the command that runs that
    file, and — for an end-user test of a titled scenario — its title check."""

    key: ScenarioKey
    selector: Selector
    place: typing.Optional[Place]
    command: typing.Optional[CommandKey]
    title: typing.Optional[TitleCheck]


class TestTable(Value):
    """The test stage's table: where it stands and the criteria its rows name, row by row."""

    place: Place
    keys: typing.Tuple[ScenarioKey, ...]
    tests: Count


class TestLocation(Value):
    """Where a mapped test was looked for: the file it was found in by its shape, or the file named after its class
    that lacks the method, or neither."""

    key: ScenarioKey
    selector: Selector
    found: typing.Optional[Place]
    candidate: typing.Optional[Place]
    shape: Detail


class PlanLevels(Value):
    """The levels the plan gave: the keys its skeleton left without one, the keys it gave `browser-only`, the keys
    it gave `integration (adapter: …)` — an incoming adapter's translation, tested against a stubbed input port by
    design."""

    unfinished: typing.Tuple[ScenarioKey, ...]
    browser_only: typing.FrozenSet[ScenarioKey]
    adapter: typing.FrozenSet[ScenarioKey]


class HandOverSize(Value):
    """A hand-over and the bytes of it the stage wrote."""

    name: HandOverName
    size: ByteSize


class HandOverName(Value):
    value: str


class ElementName(Value):
    """A domain type the plan names — `Task`, `TaskTitle`."""

    value: str


class Rule(Value):
    """One invariant of a domain type, as the plan words it — a guard included."""

    value: str


class ElementRules(Value):
    """A domain type's line under the plan's `## Invariants`: its rules, none where it says why it has none."""

    element: ElementName
    rules: typing.Tuple[Rule, ...]


class InvariantRow(Value):
    """A row of the tests' `gate:invariants` table: the type, the rule numbers it covers, and its unit test — the
    selector where one is written as `<Class>#<method>`, the text where it is not."""

    element: ElementName
    numbers: typing.Tuple[Count, ...]
    selector: typing.Optional[Selector]
    malformed: typing.Optional[Detail]


class InvariantFacts(Value):
    """What the plan says of the domain types it changes, and the tests' table of their rules."""

    listed: Count
    elements: typing.Tuple[ElementName, ...]
    named: typing.Tuple[ElementRules, ...]
    rows: typing.Optional[typing.Tuple[InvariantRow, ...]]


class Clause(Value):
    """An expectation of a scenario — its `Then` or an `And`/`But` after it — numbered from 1."""

    number: Count
    text: Detail


class ScenarioClauses(Value):
    key: ScenarioKey
    clauses: typing.Tuple[Clause, ...]


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


class AssertionFact(Value):
    """A test file's line as an assertion: what the line does, and whether the file is one of the given tests."""

    state: AssertionAt
    among: Presence


class PortName(Value):
    """A port type a test declares as a double."""

    value: str


class FileChange(enum.Enum):
    NEW = "new"
    REMOVED = "removed"


class Presence(enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"


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


class TestEdit(enum.Enum):
    """What a story did to a test that existed before it: kept it (lines added only), arranged it anew with every
    assertion kept, switched it off, or changed what it expects."""

    KEPT = "kept"
    ARRANGED = "arranged"
    SWITCHED_OFF = "switched off"
    CHANGED = "changed"

    @classmethod
    def of(cls, switched_off: Presence, lines_kept: Presence, assertions_kept: Presence) -> TestEdit:
        """An added line that switches the test off outweighs all; every line still there in its order is kept;
        every assertion still there is an arrangement; anything else changes what the test expects."""
        if switched_off is Presence.PRESENT:
            return cls.SWITCHED_OFF
        if lines_kept is Presence.PRESENT:
            return cls.KEPT
        return cls.ARRANGED if assertions_kept is Presence.PRESENT else cls.CHANGED


class ChangedTest(Value):
    place: Place
    how: TestChange


class KeptTests(Value):
    """The tests that existed before the story, against their baseline: the ones that no longer expect what they
    did, the ones whose baseline git lost, the ones changed only around their assertions."""

    changed: typing.Tuple[ChangedTest, ...]
    lost: typing.Tuple[Place, ...]
    arranged: typing.Tuple[Place, ...]


class DecidedRecord(Value):
    """An answered decision about tests: the stage that asked it, and its text."""

    record: RecordId
    stage: typing.Optional[StageName]
    text: Detail


class PlannedTestChange(Value):
    """A row of the plan's `## Changed tests`: the test, and what the row cites."""

    place: Place
    cites: Detail


class RedProof(Value):
    """The red ledger against the tests as they are: how many tests it names, how many without a file digest, the
    tests whose file changed since, and — at tidy — whether tidy reworked a test the red tree can prove again."""

    entries: Count
    unbound: Count
    moved: typing.Tuple[Detail, ...]
    reproof: Presence


class SpecDelta(Value):
    """The plan's `## Spec delta` against the story and the spec as it stands, as the spec's rules read it: what is
    wrong with it, the criteria that hold and that the story changes or removes, how many it adds and leaves."""

    plan: Place
    target: Place
    problems: typing.Tuple[Detail, ...]
    touched: typing.Tuple[ScenarioKey, ...]
    adds: Count
    holds: Count


class SpecTests(Value):
    """The tests the spec the story changes names: the moved tests that are not there, how many the spec names
    outside the story's own, and the ones of those that are gone."""

    target: Place
    absent_moved: typing.Tuple[Detail, ...]
    wanted: Count
    missing: typing.Tuple[Detail, ...]


class StoryCommit(Value):
    """The story's commit against the test files its mapping and its spec name: its short id, how many files, and
    the ones it lacks or holds otherwise than the worktree."""

    head: Detail
    files: Count
    missing: typing.Tuple[Detail, ...]


class PlannedDigest(enum.Enum):
    """The story against the digest its plan gate recorded: no digest, the story changed since, or the same."""

    MISSING = "missing"
    CHANGED = "changed"
    SAME = "same"


class PassGap(Value):
    """A stage of this pass without its hand-over: missing, or written for an earlier pass."""

    hand_over: HandOverName
    earlier: Presence


class StoryPass(Value):
    """What a delivery rests on: the stages of this pass that did not write their file after the one before, the
    judge's verdict, and the story against the one planned."""

    gaps: typing.Tuple[PassGap, ...]
    verdict: Detail
    planned: PlannedDigest


class OutcomeEvent(Value):
    """An outcome event the story publishes: the production files that declare it, and those that raise it."""

    event: EventName
    declared: typing.Tuple[Place, ...]
    raising: typing.Tuple[Place, ...]


class OutcomeFacts(Value):
    """The story's outcome events in the production code, and the files the story changed — None where no record
    says."""

    events: typing.Tuple[OutcomeEvent, ...]
    changed: typing.Optional[typing.FrozenSet[Place]]


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


class ProposalFacts(Value):
    """The terms the plan proposed, whether the project keeps a glossary, and the terms neither in one nor named
    open."""

    proposed: Count
    glossary: Presence
    missing: typing.Tuple[Detail, ...]


class ReviewFacts(Value):
    """The review perspectives: the ones with a report, without a file, with a file that is no report."""

    read: typing.Tuple[Detail, ...]
    missing: typing.Tuple[Detail, ...]
    malformed: typing.Tuple[Detail, ...]


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


class Expectation(enum.Enum):
    """What a gate expects of a story's mapped tests: red before the code exists, green after."""

    RED = "red"
    GREEN = "green"


class RunState(enum.Enum):
    """What one run said of a mapped test — or why no run could say anything."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    #: no report of the run shows it ran
    NOT_REPORTED = "not reported"
    #: the filter selects by file, and no file was located for the test
    NO_FILE = "no file"
    #: its file lies where no declared test command runs
    UNCOVERED = "uncovered"
    #: by exit code alone: the run answered like one of a test that cannot exist
    NOT_DISCRIMINATED = "not discriminated"


class Evidence(enum.Enum):
    """What a verdict rests on: the run's reports, or its exit code alone."""

    REPORT = "report"
    EXIT_CODE = "exit code"


class TestOutcome(Value):
    """One mapped test as its run left it: the command that ran it, the state, how the report showed it, the
    invocation (and, where it ran alone after a shared run missed it, that invocation), the exit code, the end of
    the output, how many cases the report held, and whether a red came from a timeout."""

    key: ScenarioKey
    selector: Selector
    place: typing.Optional[Place]
    command: typing.Optional[CommandKey]
    state: RunState
    evidence: Evidence
    how: Detail
    invocation: Detail
    alone: typing.Optional[Detail]
    code: Count
    output: Detail
    cases: Count
    timeout: Presence


class RunEnd(Value):
    """The end of one invocation's outcomes — shared where it carried several tests."""

    invocation: Detail
    shared: Presence


class TestRun(Value):
    """A gate's run of the mapped tests: whether the profile names a test command at all, and what each
    invocation said, in order."""

    command: Presence
    items: typing.Tuple[typing.Union[TestOutcome, RunEnd], ...]


class RedLedger(Value):
    """The red ledger as a run reads it: whether there is one (and its name), the tests it names, the decisions and
    corrections that changed an expectation, whether an earlier pass's build met the tests, and the tests whose file
    changed since they were seen red."""

    present: Presence
    name: Detail
    was_red: typing.FrozenSet[Selector]
    changed_on: typing.Tuple[RecordId, ...]
    built_before: Presence
    moved: typing.FrozenSet[Selector]


class CommandRun(Value):
    """One run of a profile command: the command, its exit code, the end of its output, and where it came from when
    the gate did not start it."""

    command: Detail
    code: Count
    output: Detail
    reused: Detail


class Retried(Value):
    """A red test outside the story, run again alone: the test and the invocation that ran it."""

    test: Detail
    alone: Detail


class SuiteRun(Value):
    """A test command run whole: its key, the run, how many cases ran and failed by its reports (after a retry of
    red tests outside the story), the ones green alone (flaky), the ones red again, and whether its exit code is
    the only evidence the profile allows."""

    key: Detail
    run: CommandRun
    executed: Count
    failed: Count
    flaky: typing.Tuple[Retried, ...]
    still: typing.Tuple[Retried, ...]
    exit_code_only: Presence


class SuiteCommands(Value):
    """The test commands the profile declares and the ones its policy requires: every key a run may need, with its
    command where the profile names one."""

    declared: typing.Tuple[typing.Tuple[CommandKey, typing.Optional[Detail]], ...]
    required: typing.FrozenSet[CommandKey]


class Snapshot(Value):
    """The commit's index against the working tree: why no tree could be written, the tree, what differs from it
    outside the pipeline's own and the tools' folders, and how many files the pipeline wrote itself."""

    refused: typing.Optional[Detail]
    tree: Detail
    drift: typing.Tuple[Detail, ...]
    left: Count


class ParityScenario(Value):
    """A scenario of a parity contract: its id, its title — what binds it to a test — and whether every
    configuration has to prove it."""

    id: Detail
    title: Detail
    always: Presence


class ImplementationReports(Value):
    """One implementation's reports: its name, the glob, how many reports match, the newest, and the outcome each
    test name has in them."""

    name: Detail
    glob: Detail
    reports: Count
    newest: Detail
    outcomes: typing.Tuple[typing.Tuple[Detail, Detail], ...]


class ParityFacts(Value):
    """A parity config: its file, the contract's file and digest, its scenarios, and each implementation's
    reports."""

    config: Place
    scenarios_file: Detail
    digest: Detail
    scenarios: typing.Tuple[ParityScenario, ...]
    implementations: typing.Tuple[ImplementationReports, ...]
