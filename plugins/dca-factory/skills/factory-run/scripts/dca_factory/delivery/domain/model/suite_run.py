"""The runs of the profile's test commands: what a check requires, each run and its tests, the red ledger."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .decision_record import RecordId
from .story_state import Detail
from .story_words import Count, Place, Presence, ScenarioKey, Selector
from .verdict import CheckName, Finding, Findings, Said


#: The check over a suite's commands and runs.
SUITE = CheckName("suite")


class Requirement(enum.Enum):
    """How the project's policy ranks a check: no policy declared — every check decides —, required by it, or
    declared and not named in it — optional."""

    UNDECLARED = "undeclared"
    REQUIRED = "required"
    OPTIONAL = "optional"

    def red(self, check: CheckName, said: Said) -> Finding:
        """A red check fails the verdict — unless it is optional: the red run is reported, and it is not what the
        commit is judged by."""
        if self is Requirement.OPTIONAL:
            return check.note(Said(said.value + " — optional (not in `required:`), so it does not decide"))
        return check.fail(said)


class CommandKey(Value):
    """A profile key of a test command — `test`, `e2eTest`, `test.journey`."""

    value: str

    def missing(self, check: CheckName) -> Finding:
        """The check skipped: the profile names no command under this key."""
        return check.skip(Said(f"no `{self.value}:` command in the stack profile"))


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

    def verdict(self, check: CheckName, requirement: Requirement) -> Finding:
        """A command a change's checks run: green passes; red fails — unless the policy ranks it optional."""
        if self.code.value == 0:
            return check.ok(Said(f"`{self.command.value}` succeeded"))
        return requirement.red(check, Said(f"`{self.command.value}` failed:\n{self.output.value}"))


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
