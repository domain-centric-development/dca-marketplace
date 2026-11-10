"""Check one stage of a story's run: every check the stage table registers for the stage, those that start no
process first, and — where all of them pass — what a passing gate does."""

from __future__ import annotations

import typing

from ...domain.model.jump import Jump
from ...domain.model.stage import ALL_KINDS, Stage, StoryKind, Trait
from ...domain.model.verdict import FindingState, Findings
from ...domain.model.workflow import Workflow
from ...domain.model.workflow_rule import OutcomeState, RulePart
from .pipeline_rules import bind, Bound, DECIDED, restage, rule_of
from .pipeline_workflow import loaded, on_load, workflow

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
        #: the mapped tests a refused test check names, each once — what the journal keeps of a refusal beside its
        #: checks, so a repeated refusal is told from another after the reports are pruned
        self.failing_tests: typing.List[str] = []
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


#: Which stages a check holds: None — every gated stage, names of rows, or a predicate over a row.
Stages = typing.Union[None, typing.Tuple[str, ...], typing.Callable[[Stage], bool]]


class Check(typing.NamedTuple):
    name: str
    run: CheckRun
    #: the stages it holds, placed once the workflow is loaded (`place`)
    stages: typing.Tuple[str, ...]
    needs_process: bool
    #: the check names a refusal before it leaves unproven
    unrun: typing.Callable[[Run], typing.List[str]]
    #: the story kinds it holds (a task has no criteria, so none of their checks)
    kinds: typing.FrozenSet[StoryKind]
    #: the rules it holds the story to, by id — one per name it reports under
    rules: typing.Tuple[Bound, ...]
    #: what it said about its stages where it registered
    select: Stages = None


#: The checks a gate run holds a story to, in this order: every check that needs no process first, and a refusal among
#: them ends the run before a suite starts — a file list that is wrong is wrong in a millisecond, not after a minute of
#: tests. What did not run is named, so the report says what is still unproven.
CHECKS: typing.List[Check] = []

#: The order the checks run in, whichever module registers them: the story and the profile first, then what the
#: stage left, the tests last.
ORDER = ("story", "contract", "status", "epic", "outcome", "rounds", "suites", "decisions", "plan", "guarded", "plan-adopts", "document",
         "pipeline", "owned", "brief", "adopt", "integrate", "tests-mapped", "files-listed", "test-design", "spec-delta",
         "spec-tests", "tests-committed", "tests-real", "tests-assert-then", "plan-files", "size", "red-proof", "tests", "invariant-breaks",
         "red-reproof", "commands")

#: What a passing gate does, per stage — the writes a verdict makes.
PASSED: typing.Dict[str, typing.List[CheckRun]] = {}
#: The rules of what a passing gate does, per stage.
PASS_RULES: typing.Dict[str, typing.List[Bound]] = {}

#: One rule's id, or several.
Rules = typing.Union[str, typing.Tuple[str, ...]]



def chosen_stages(name: str, stages: Stages, workflow: Workflow) -> typing.Tuple[str, ...]:
    """The gated stages of <workflow> a check holds."""
    gated = workflow.having(Trait.GATED)
    if stages is None:
        return tuple(s.name.value for s in gated)
    if callable(stages):
        return tuple(s.name.value for s in gated if stages(s))
    unknown = [stage for stage in stages if stage not in {s.name.value for s in gated}]
    if unknown:
        raise ValueError(f"check {name}: no gated stage {', '.join(unknown)}")
    return tuple(stages)


def place(workflow: Workflow) -> None:
    """Place every check and every pass action against the stages of <workflow>."""
    CHECKS[:] = [placed(c, workflow) for c in CHECKS]
    unknown = sorted(set(PASSED) - {s.name.value for s in workflow.having(Trait.GATED)})
    if unknown:
        raise ValueError(f"on_pass: no gated stage {', '.join(unknown)}")


def placed(entry: Check, workflow: Workflow) -> Check:
    chosen = chosen_stages(entry.name, entry.select, workflow)
    return entry._replace(stages=chosen, rules=restage(entry.rules, chosen))


def check(name: str, stages: Stages = None, needs_process: bool = False,
          unrun: typing.Optional[typing.Callable[[Run], typing.List[str]]] = None,
          kinds: typing.FrozenSet[StoryKind] = ALL_KINDS, *, rule: Rules) -> typing.Callable[[CheckRun], CheckRun]:
    """Register a check against the workflow's stages: `stages` names rows (None — every gated stage) or is a
    predicate over a row, placed once the workflow is loaded; `kinds` the story kinds it holds; `rule` what it holds
    the story to — one rule, or one per name it reports under, by id. A check without a rule is no check: the rulebook
    could not show it."""
    if name not in ORDER:
        raise ValueError(f"check {name}: not in the checks' order")

    rules = (rule,) if isinstance(rule, str) else rule
    if not rules or not all(r.startswith("GATE-") for r in rules):
        raise ValueError(f"check {name}: carries its rules, each a GATE- id")

    def register(function: CheckRun) -> CheckRun:
        entry = Check(name, function, (), needs_process, unrun or (lambda run: [name]), kinds,
                      bind(rules, RulePart.CHECK, function, (), kinds), stages)
        CHECKS.append(placed(entry, workflow()) if loaded() else entry)
        CHECKS.sort(key=lambda c: ORDER.index(c.name))
        return function
    return register


def on_pass(stage: str, *, rule: Rules) -> typing.Callable[[CheckRun], CheckRun]:
    """Register what a passing gate of the stage does, and the rules it does it by — a gated stage of the workflow,
    held once it is loaded."""
    rules = (rule,) if isinstance(rule, str) else rule

    def register(function: CheckRun) -> CheckRun:
        PASSED.setdefault(stage, []).append(function)
        PASS_RULES.setdefault(stage, []).extend(bind(rules, RulePart.PASS, function, (stage,)))
        return function
    return register


on_load(place)


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


def judging(stage: str, kind: StoryKind) -> typing.Tuple[str, ...]:
    """The rules a gate of <stage> holds a story of <kind> to, in the order its checks run — each once."""
    found: typing.List[str] = []
    for entry in CHECKS:
        if stage in entry.stages and kind in entry.kinds:
            found += [b.rule for b in entry.rules if b.rule not in found]
    return tuple(found)


def refusing(stage: str, names: typing.Iterable[str]) -> typing.Tuple[Jump, ...]:
    """The ways of the rules a gate of <stage> refused under <names> (the checks its report says failed): the rules of
    the stage's checks, of what its passing gate does, and of the gate's own frame — each once, in the report's order."""
    if not CHECKS:
        raise RuntimeError("no gate check is registered — the composition root imports the modules of checks")
    bound = [b for c in CHECKS if stage in c.stages for b in c.rules] + PASS_RULES.get(stage, []) \
        + [b for b in DECIDED if b.rule.startswith("GATE-")]
    found: typing.List[str] = []
    for name in names:
        found += [b.rule for b in bound if b.rule not in found
                  and name in {r.value for r in rule_of(b.rule).reports}]
    return tuple(rule_of(rule_id).jump(OutcomeState.FAIL) for rule_id in found)
