"""The story as a stage's gate reads it, and the facts its checks are handed."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Value
from .story import StoryContent as StoryContent
from .story_words import Count as Count, ScenarioKey as ScenarioKey, RowId as RowId, EventName as EventName, Clause as Clause, ScenarioClauses as ScenarioClauses, Place as Place
from .decision_record import RecordId
from .epic import EpicId
from .schedule import ContextName
from .stage import StageName
from .story_state import Detail, HandOverText, Rounds
from .verdict import CheckName, Finding, Findings, Said


class RowState(Value):
    """Where a finding row stands: `open`, or what closed it."""

    value: str


#: A finding row nobody closed yet — the only one a task may close; its delivery sets the row to DONE_ROW.
OPEN_ROW = RowState("open")
DONE_ROW = RowState("done")


class FindingKey(Value):
    """What makes a kept finding the same as another: where it is (`file:line`) and the defect it names. A delivery
    keeps each finding not kept already — the same place and defect is one finding, however often a later round
    confirms it."""

    place: Place
    defect: Detail


class ContractNumber(Value):
    """A gate contract: what the gate reads and writes, raised when that changes incompatibly."""

    value: int


#: The checks over the profile: the contract the gate reads it as, the keys nobody reads, the instruction file's size.
CONTRACT_CHECK = CheckName("contract")
PROFILE = CheckName("profile")
INSTRUCTION_SIZE = CheckName("instruction-size")
#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools have comparable
#: budgets.
DOC_BUDGET_BYTES = 32 * 1024


class GateRelease(Value):
    """The gate that checks: the contract it implements and its version."""

    contract: ContractNumber
    version: Detail

    def reads(self, declared: ProfileText) -> ContractNumber:
        """The contract a profile is read as: the one it declares, else the gate's own."""
        text = declared.value.strip()
        return ContractNumber(int(text)) if text.isdigit() else self.contract

    def profile_findings(self, declared_text: ProfileText, unknown: typing.Sequence[UnknownKey]) -> Findings:
        """Undeclared is the normal case and only a note: a profile with today's keys is what the template writes. A
        *higher* number than this gate knows is a refusal — the project has keys this gate would ignore, and ignoring a
        key silently is how a check disappears without anyone noticing. A key outside the profile's schema is a note,
        named with the nearest known key: nobody reads it, which is worth knowing and no reason to stop a story."""
        found = [PROFILE.note(Said(f"`{u.key.value}:` is no key the pipeline reads — ignored"
                                   + (f"; did you mean `{u.near.value}:`?" if u.near else "")))
                 for u in unknown]
        ours, version = self.contract.value, self.version.value
        declared = declared_text.value.strip()
        if not declared:
            found.append(CONTRACT_CHECK.note(Said(f"profile declares no `contract:` — read as {ours} (gate {version})")))
        elif not declared.isdigit():
            found.append(CONTRACT_CHECK.fail(Said(f"profile's `contract: {declared}` is not a number")))
        elif int(declared) > ours:
            found.append(CONTRACT_CHECK.fail(Said(
                f"the profile is written for gate contract {declared} and this gate implements {ours} (gate {version}) "
                f"— run `factory.sh update` before trusting a run, because this script would ignore whatever the newer "
                f"contract added")))
        elif int(declared) < ours:
            found.append(CONTRACT_CHECK.note(Said(
                f"the profile declares contract {declared} and this gate implements {ours} (gate {version}) — still "
                f"read, and worth bringing up to date")))
        else:
            found.append(CONTRACT_CHECK.ok(Said(f"profile and gate agree on contract {ours} (gate {version})")))
        return tuple(found)


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


class BriefFacts(Value):
    """Which brief a stage worked from: the digest of the one the runner gave it — None where it gave none, a stage
    run by hand —, the one its hand-over <place> names — None where it names none."""

    place: Place
    given: typing.Optional[Detail]
    named: typing.Optional[Detail]

    def findings(self) -> Findings:
        """A stage the runner gave a brief names it in its hand-over: one that worked from another brief, or names
        none, is refused — what it was told is not what it did."""
        if self.given is None:
            return ()
        if self.named is None:
            return (CheckName("brief").fail(Said(
                f"{self.place.value} names no brief — end it with the line `brief: {self.given.value}`, the digest "
                f"the brief you were given ends with, after reading that brief")),)
        if self.named != self.given:
            return (CheckName("brief").fail(Said(
                f"{self.place.value} names the brief {self.named.value}, but the stage was given "
                f"{self.given.value} — read the brief you were given and work by it")),)
        return (CheckName("brief").ok(Said(f"the stage worked from the brief it was given ({self.given.value})")),)


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

    def size_findings(self) -> Findings:
        """A note, not a check: instructions past a tool's document budget are truncated silently, so a run can be
        missing half its rules without anything saying so."""
        name, size = self.place.value, self.size.value
        if size > DOC_BUDGET_BYTES:
            return (INSTRUCTION_SIZE.skip(Said(
                f"{name} is {size} bytes, past the {DOC_BUDGET_BYTES}-byte budget some tools load — the rest is "
                f"truncated silently; move detail into referenced files")),)
        return (INSTRUCTION_SIZE.ok(Said(f"{name} is {size} bytes, within a tool's budget")),)


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


class HandOverAsk(Value):
    """A stage's hand-over as the decisions check reads it: its text, and the records its `## needs-human` names —
    None where it escalates nothing, none where it escalates without naming one."""

    stage: StageName
    place: Place
    text: HandOverText
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


class DecisionsFacts(Value):
    """The store of the story's decision records, and the stages' hand-overs — or why the store cannot be read. The
    records themselves are aggregates, read on their own (`StageEvidence.decision_records`)."""

    store: Place
    hand_overs: typing.Tuple[HandOverAsk, ...]
    unreadable: typing.Optional[Detail] = None


#: The form of a test's name in the tests table: the fully qualified class, then the test method.
SELECTOR_FORM = re.compile(r"^([\w.]+)#([\w]+)$")


class Selector(Value):
    """A test as the tests table names it: `<Class>#<method>`."""

    value: str


#: The check over a suite's commands and runs.
SUITE = CheckName("suite")


def red(check: CheckName, said: Said, must: Presence, strict: Presence) -> Finding:
    """A red check fails the verdict — unless a policy is declared and this check is not in it. Then the policy
    decides: the red run is reported, and it is not what the commit is judged by."""
    if strict is Presence.PRESENT and must is Presence.ABSENT:
        return check.note(Said(said.value + " — optional (not in `required:`), so it does not decide"))
    return check.fail(said)


class CommandKey(Value):
    """A profile key of a test command — `test`, `e2eTest`, `test.journey`."""

    value: str

    def missing(self, check: CheckName) -> Finding:
        """The check skipped: the profile names no command under this key."""
        return check.skip(Said(f"no `{self.value}:` command in the stack profile"))


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

    def finding(self) -> Finding:
        """A selector must point at a test that is actually there. Without this check a missing test looks exactly
        like a red one, and the run would certify nothing."""
        selector, key = self.selector.value, self.key.value
        cls, _sep, method = selector.partition("#")
        if self.found is not None:
            return (CheckName("tests-exist").ok(Said(f"{selector} found in {self.found.value} ({key}, by "
                                             f"{self.shape.value})")))
        elif self.candidate is not None:
            return (CheckName("tests-exist").fail(Said(
                f"{selector}: {self.candidate.value} has no {method} — criterion {key!r} has no test, only a row "
                f"in the table")))
        else:
            return (CheckName("tests-exist").fail(Said(
                f"{selector}: no source file for {cls.rsplit('.', 1)[-1]} — criterion {key!r} has no test, and a "
                f"missing test is indistinguishable from a red one at the runner")))


class PlanLevels(Value):
    """The levels the plan gave: the keys its skeleton left without one, the keys it gave `browser-only`, the keys
    it gave `integration (adapter: …)` alone — an incoming adapter's translation, tested against a stubbed input
    port by design — and the keys it gave both shapes, the adapter's beside one through the real input port."""

    unfinished: typing.Tuple[ScenarioKey, ...]
    browser_only: typing.FrozenSet[ScenarioKey]
    adapter: typing.FrozenSet[ScenarioKey]
    both: typing.FrozenSet[ScenarioKey]


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


class ShownLiteral(Value):
    """A text an expectation quotes as what is shown — „…“, "…", “…”, ‚…‘, ‘…’ or «…» — not one that names an element
    the step points at (a button, a field, a form, a link, or what is pressed or clicked)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("a shown literal says something")


class TestSource(Value):
    """The whole text of a test's file — a literal often stands in a constant, not in the test's method."""

    value: str

    def says(self, literal: ShownLiteral) -> bool:
        """Whether the file carries the literal as written, or with its straight quotes escaped as a string
        literal of the language writes them."""
        text = literal.value
        return text in self.value or ('"' in text and text.replace('"', '\\"') in self.value)


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


class AdoptRow(Value):
    """A scenario the plan found holding on today's code alone, with the test that shows it."""

    key: ScenarioKey
    test: Selector
    present: Presence


class PlanAdoption(Value):
    """The plan's `## Adopt`: the scenarios of the story that hold already and no delivered story carries."""

    rows: typing.Tuple[AdoptRow, ...]


class SymbolName(Value):
    """A type or a method as the source names it — `OrderChangedSinceReviewException`, `openFindings`."""

    value: str


class Rename(Value):
    """A name the story gave a type or a method: its old declaration gone from the sources, its new one present."""

    was: SymbolName
    now: SymbolName
    #: whether a context's glossary names the new name — the ubiquitous language's, or only the code's
    in_glossary: Presence


class RenamedTest(Value):
    """A test that holds every assertion it had once the names the story renamed are read under their new names."""

    place: Place
    renames: typing.Tuple[Rename, ...]


class KeptTests(Value):
    """The tests that existed before the story, against their baseline: the ones that no longer expect what they
    did, the ones whose baseline git lost, the ones changed only around their assertions, the ones that follow a
    rename."""

    changed: typing.Tuple[ChangedTest, ...]
    lost: typing.Tuple[Place, ...]
    arranged: typing.Tuple[Place, ...]
    renamed: typing.Tuple[RenamedTest, ...] = ()


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

    def finding(self, check: CheckName) -> Finding:
        """A command the stage's gate looks up and runs: it passes or it fails."""
        if self.code.value == 0:
            return check.ok(Said(f"`{self.command.value}` succeeded{self.reused.value}"))
        return check.fail(Said(f"`{self.command.value}` failed:\n{self.output.value}"))

    def verdict(self, check: CheckName, must: Presence, strict: Presence) -> Finding:
        """A command a change's checks run: green passes; red fails — unless a policy is declared that does not
        name this check (`red`)."""
        if self.code.value == 0:
            return check.ok(Said(f"`{self.command.value}` succeeded"))
        return red(check, Said(f"`{self.command.value}` failed:\n{self.output.value}"), must, strict)


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

    def required_findings(self) -> Findings:
        """The test commands the policy requires: a required key without its command fails — silently passed, the
        stage gate would certify a suite nobody can run."""
        if not self.required:
            return ()
        found = [SUITE.fail(Said(f"no `{key.value}:` command in the stack profile — and `{key.value}` is required"))
                 for key, command in self.declared if key in self.required and command is None]
        if not any(key in self.required for key, _command in self.declared):
            found.append(SUITE.skip(Said("`required:` names no declared test command")))
        return tuple(found)

    def task_findings(self) -> Findings:
        """A task proves itself on the existing suite: the profile has to declare a test command."""
        if any(command is not None for _key, command in self.declared):
            return ()
        return (SUITE.fail(Said("a task proves itself on the existing suite, and the stack profile declares no test "
                                "command — declare `test:` (and its siblings)")),)
