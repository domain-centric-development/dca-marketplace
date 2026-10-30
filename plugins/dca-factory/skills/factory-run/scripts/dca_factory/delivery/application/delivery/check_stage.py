"""Check one stage of a story's run: every check the stage table registers for the stage, those that start no
process first, and — where all of them pass — what a passing gate does."""

from __future__ import annotations

import typing

from ...domain.model.stage import ALL_KINDS, PIPELINE, Stage, StoryKind, Trait
from ...domain.model.verdict import FindingState, Findings

Entry = typing.Tuple[str, str, str]
Run = typing.Any
#: A check's run over a stage's gate run; it leaves its findings in the run's verdict.
CheckRun = typing.Callable[[Run], typing.Any]


class Verdict:
    """What one gate run found, finding by finding (`pass`, `fail`, `skip`, `note`, `wait`), and what its delivery
    wrote: the files a delivery wrote into the project, the tests outside the story red in a whole run and green
    alone, and whether a delivery journaled its passing verdict before its commit."""

    def __init__(self) -> None:
        self.entries: typing.List[Entry] = []
        self.written: typing.List[str] = []
        self.flaky: typing.List[str] = []
        self.closed = False

    def ok(self, check: str, message: str) -> None:
        self.entries.append(("pass", check, message))

    def fail(self, check: str, message: str) -> None:
        self.entries.append(("fail", check, message))

    def skip(self, check: str, message: str) -> None:
        self.entries.append(("skip", check, message))

    def note(self, check: str, message: str) -> None:
        """A fact worth reading that fails nothing and covers nothing — it is not a skipped check."""
        self.entries.append(("note", check, message))

    def wait(self, check: str, message: str) -> None:
        """Nothing failed, and a human has to answer before the story goes on — exit 3, not 0."""
        self.entries.append(("wait", check, message))

    def take(self, findings: Findings) -> None:
        """A domain check's findings, as the gate reports them."""
        for finding in findings:
            self.entries.append((finding.state.value, finding.check.value, finding.said.value))

    @property
    def waiting(self) -> bool:
        return any(state == FindingState.WAIT.value for state, _, _ in self.entries)

    @property
    def failed(self) -> bool:
        return any(state == FindingState.FAIL.value for state, _, _ in self.entries)


class StageRun:
    """What one gate run over a story knows — its stage, the story, the evidence, the verdict —; the registered
    checks read it and leave their findings in `result` (and the mapping and the located tests for the checks after
    them)."""

    def __init__(self, **fields: typing.Any) -> None:
        self.mapping: typing.Dict[str, typing.List[str]] = {}
        self.located: typing.Dict[str, str] = {}
        self.__dict__.update(fields)


class Check(typing.NamedTuple):
    name: str
    run: CheckRun
    stages: typing.Tuple[str, ...]
    needs_process: bool
    #: the check names a refusal before it leaves unproven
    unrun: typing.Callable[[Run], typing.List[str]]
    #: the story kinds it holds (a task has no criteria, so none of their checks)
    kinds: typing.FrozenSet[StoryKind]


#: The checks a gate run holds a story to, in this order: every check that needs no process first, and a refusal among
#: them ends the run before a suite starts — a file list that is wrong is wrong in a millisecond, not after a minute of
#: tests. What did not run is named, so the report says what is still unproven.
CHECKS: typing.List[Check] = []

#: The order the checks run in, whichever module registers them: the story and the profile first, then what the
#: stage left, the tests last.
ORDER = ("story", "contract", "status", "epic", "outcome", "rounds", "suites", "decisions", "plan", "plan-adopts", "document",
         "pipeline", "owned", "adopt", "integrate", "tests-mapped", "files-listed", "test-design", "spec-delta",
         "spec-tests", "tests-committed", "tests-real", "plan-files", "size", "red-proof", "tests", "invariant-breaks",
         "red-reproof", "commands")

#: What a passing gate does, per stage — the writes a verdict makes.
PASSED: typing.Dict[str, typing.List[CheckRun]] = {}

GATED = tuple(s for s in PIPELINE if Trait.GATED in s.traits)


def check(name: str, stages: typing.Union[None, typing.Tuple[str, ...], typing.Callable[[Stage], bool]] = None,
          needs_process: bool = False, unrun: typing.Optional[typing.Callable[[Run], typing.List[str]]] = None,
          kinds: typing.FrozenSet[StoryKind] = ALL_KINDS) -> typing.Callable[[CheckRun], CheckRun]:
    """Register a check against the stage table: `stages` names rows (None — every gated stage) or is a predicate
    over a row; `kinds` the story kinds it holds."""
    if stages is None:
        chosen = tuple(s.name.value for s in GATED)
    elif callable(stages):
        chosen = tuple(s.name.value for s in GATED if stages(s))
    else:
        known = {s.name.value for s in GATED}
        unknown = [stage for stage in stages if stage not in known]
        if unknown:
            raise ValueError(f"check {name}: no gated stage {', '.join(unknown)}")
        chosen = tuple(stages)

    if name not in ORDER:
        raise ValueError(f"check {name}: not in the checks' order")

    def register(function: CheckRun) -> CheckRun:
        CHECKS.append(Check(name, function, chosen, needs_process, unrun or (lambda run: [name]), kinds))
        CHECKS.sort(key=lambda c: ORDER.index(c.name))
        return function
    return register


def on_pass(stage: str) -> typing.Callable[[CheckRun], CheckRun]:
    """Register what a passing gate of the stage does."""
    if stage not in {s.name.value for s in GATED}:
        raise ValueError(f"on_pass: no gated stage {stage}")

    def register(function: CheckRun) -> CheckRun:
        PASSED.setdefault(stage, []).append(function)
        return function
    return register


def run_checks(run: Run) -> None:
    """The stage's checks over the run: those that start no process first; a refusal among them leaves the others
    unrun and named."""
    kind = StoryKind(run.kind)
    chosen = [c for c in CHECKS if run.stage.name in c.stages and kind in c.kinds]
    for entry in (c for c in chosen if not c.needs_process):
        entry.run(run)
    process = [c for c in chosen if c.needs_process]
    if run.result.failed and process:
        refused = sorted({name for state, name, _m in run.result.entries if state == "fail"})
        for entry in process:
            for name in entry.unrun(run):
                run.result.skip(name, f"not run — {', '.join(refused)} refused first; fix that, then it runs")
        return
    for entry in process:
        entry.run(run)


def run_passed(run: Run) -> None:
    """What a passing gate of the run's stage does."""
    for finish in PASSED.get(run.stage.name, ()):
        finish(run)
