"""The checks a stage's gate runs processes for — the mapped tests, the suites and the stage's commands, a test's
break on a scratch copy, a rule's test, a test tidy moved, re-proved on the red tree, and the adopt gate — over the
output port StageRuns, each outcome judged by a domain service."""

from __future__ import annotations

import re
import typing

from ...domain.model.stage import Stage, StageName, StoryKind, Trait
from ...domain.model.stage_story import (
    CommandKey, ContractNumber, Expectation, MappedTest, Place, Presence, ScenarioKey, Selector, SELECTOR_FORM,
    StageStory)
from ...domain.model.story_state import Detail
from ...domain.model.verdict import CheckName, Finding, FindingState, Findings, Said
from ...domain.gateway.stage_evidence import StageEvidence
from ...domain.service.break_checks import BreakChecks, BreakOutcome, BreakResult
from ...domain.service.design_checks import DesignChecks
from ...domain.service.kept_checks import KeptChecks
from ...domain.service.suite_checks import SuiteChecks
from ...domain.service.test_verdicts import BreakProof, TestVerdicts
from ..shared.stage_runs import Located, Mapping, StageRuns, WholeRuns
from .check_stage import check, Run, Verdict
from .stage_checks import read_table, table_tests

COMPILES = CheckName("compiles")
#: The contract that holds an adoption's rules' tests to green beside its scenarios, and the one that proves every
#: rule of a story's domain types by its break.
ADOPTED_RULES_CONTRACT = ContractNumber(24)
INVARIANT_BREAKS_CONTRACT = ContractNumber(25)
OUTSIDE = "outside the table"


def presence(held: bool) -> Presence:
    return Presence.PRESENT if held else Presence.ABSENT


def findings_of(probe: Verdict, check_name: str, about: typing.Optional[str] = None) -> Findings:
    """A verdict's entries of one check as findings — of one test, where `about` names it."""
    return tuple(Finding(FindingState(state), CheckName(c), Said(m)) for state, c, m in probe.entries
                 if c == check_name and (about is None or m.startswith(about + " ") or m.startswith(about + ":")))


def test_state(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], mapping: Mapping,
               expected: str, located: typing.Optional[Located] = None, story: typing.Optional[str] = None,
               guard: bool = False, whole_for: typing.Iterable[str] = (),
               red_proof: typing.Optional[typing.Tuple[StageStory, StageEvidence]] = None) -> WholeRuns:
    """Expected 'red': every mapped test must fail; 'green': all must pass (`TestVerdicts`) — the tests run first,
    their outcomes judged against the red ledger. A break proof the judgement asks for is run here; a test it proves
    counts as red, one it does not keeps its earlier proof. Returns the commands run whole, so the suite check reads
    them rather than running them again. `red_proof` — the story and its evidence — holds a green run's tests to the
    versions seen red."""
    located = located or {}
    if (profile.get("e2eTest") or profile.get("test")) and not mapping:
        return {}
    test_run, whole_runs = runs.tests(mapping or {}, located, whole_for)
    ledger = runs.ledger(story, expected == "red", located)
    judged = TestVerdicts.judge(Expectation(expected), presence(guard), test_run, ledger)
    now_red, kept = {s.value for s in judged.now_red}, {}
    for item in judged.items:
        if not isinstance(item, BreakProof):
            result.take((item,))
            continue
        probe = Verdict()
        break_proof(probe, runs, profile, story or "", item.selector.value, item.key.value, located)
        result.entries.extend(probe.entries)
        if not probe.failed:
            now_red.add(item.selector.value)
        else:
            # The earlier proof stands for the version it was taken against; losing it would make the next run treat
            # this test as one never seen red, which no break can repair.
            kept[item.selector.value] = runs.digests(story).get(item.selector.value)
    if test_run.command is Presence.ABSENT:
        return whole_runs
    if expected == "red":
        runs.write_ledger(story, now_red, located, kept)
    elif ledger.present is Presence.PRESENT and red_proof is not None:
        tests = tuple(MappedTest(ScenarioKey(""), Selector(selector), Place(path), None, None)
                      for selector, path in located.items() if path)
        result.take(KeptChecks.red_proof(red_proof[0], StageName(""), tests, red_proof[1]))
    return whole_runs


def run_break(runs: StageRuns, profile: typing.Mapping[str, typing.Any], copy: str, scratch: str, patch: str,
              selector: str, key: str, located: Located) -> BreakResult:
    """One break on a scratch copy the caller made: applied, the one test run, taken back — so the next break on the
    same copy builds on what this one compiled."""
    code, said = runs.apply(copy, scratch, patch)
    if code != 0:
        return BreakResult(BreakOutcome.UNAPPLIED, Detail(said[:200]))
    try:
        probe = Verdict()
        test_state(probe, runs.on(copy), profile, {key: [selector]}, "red",
                   {selector: located[selector]} if located.get(selector) else {})
        return BreakChecks.verdict(findings_of(probe, "tests-red"))
    finally:
        runs.apply(copy, scratch, patch, reverse=True)


def break_proof(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], story: str,
                selector: str, key: str, located: Located,
                copied: typing.Optional[typing.Tuple[str, str]] = None) -> None:
    """A test green without ever being seen red, held to its break (`BreakChecks.proof`)."""
    patch = runs.patch(story, selector)
    outcome = None
    if patch and copied:
        outcome = run_break(runs, profile, copied[0], copied[1], patch, selector, key, located)
    elif patch:
        with runs.scratch() as (copy, scratch):
            outcome = run_break(runs, profile, copy, scratch, patch, selector, key, located)
    result.take((BreakChecks.proof(Selector(selector), Detail(key), outcome, Place(runs.patch_place(story, selector))),))


def invariant_breaks(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], story: str,
                     mapping: typing.Optional[Mapping]) -> None:
    """Every rule the plan names is shown to be guarded by its unit test. Its test seen red before the build proves it
    as a criterion's red run does; one green already — the rule exists — needs its break, one change to the
    production code that turns it red. All breaks of the gate run on one scratch copy, each running its one test, so
    the second compiles on the first. A survived or missing break is refused."""
    criterion = {sel for sels in (mapping or {}).values() for sel in sels}
    rules: typing.Dict[str, typing.List[typing.Tuple[str, typing.List[int]]]] = {}
    for element, numbers, selector in runs.invariant_rows(story) or []:
        if selector and SELECTOR_FORM.match(selector) and selector not in criterion:
            rules.setdefault(selector, []).append((element, numbers))
    if not rules:
        return
    keys = {sel: "; ".join(f"{e} rule {', '.join(map(str, n))}" for e, n in owners) for sel, owners in rules.items()}
    located = runs.locate({keys[sel]: [sel] for sel in rules})
    probe = Verdict()
    test_state(probe, runs, profile, {keys[sel]: [sel] for sel in sorted(rules)}, "red", located)
    before = {sel: BreakChecks.verdict(findings_of(probe, "tests-red", sel)) for sel in rules}
    green = [sel for sel in sorted(rules) if before[sel].outcome is BreakOutcome.GREEN]
    proofs = {}

    def prove(copied: typing.Tuple[str, str]) -> None:
        for sel in sorted(rules):
            under = None
            if sel in green:
                patch = runs.patch(story, sel)
                under = run_break(runs, profile, copied[0], copied[1], patch, sel, keys[sel], located) if patch else None
            proofs[sel] = BreakChecks.rule_proof(before[sel], under)
    if green:
        with runs.scratch() as copied:
            prove(copied)
    else:
        prove(("", ""))
    runs.rule_proofs(story, [(e, n, sel, proofs[sel].value) for sel, owners in sorted(rules.items()) for e, n in owners])
    for sel in sorted(rules):
        said = "; ".join(m for _st, _c, m in probe.entries if sel in m)
        result.take((BreakChecks.invariant(Selector(sel), Detail(keys[sel]), proofs[sel],
                                           Place(runs.patch_place(story, sel)), Detail(said)),))


def compiles(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any]) -> None:
    """The profile's `compile:` command passes (`SuiteChecks.command`)."""
    command = profile.get("compile")
    result.take((SuiteChecks.command(COMPILES, runs.command(command)) if command
                 else SuiteChecks.missing(COMPILES, CommandKey("compile")),))


def reproof(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], story: str,
            mapping: typing.Optional[Mapping], located: typing.Optional[Located]) -> None:
    """At the tidy gate: a test tidy moved is run on the red tree with the working tree's tests laid over it. Red
    there (an assertion's red, not a timeout), its new version carries the proof: the ledger takes its digest and the
    journal a `red-reproved` line. Green there, or not compiling (tidy renamed production code the test calls), it is
    refused."""
    if runs.answered_tests(story):
        return
    located = located or {}
    moved = runs.tidy_moves(story, located)
    tree = runs.red_tree(story)
    if not moved or not tree:
        return
    keys = {selector: key for key, selectors in (mapping or {}).items() for selector in selectors}
    table: typing.Dict[str, typing.List[str]] = {}
    for selector in moved:
        table.setdefault(keys.get(selector, "moved by tidy"), []).append(selector)
    with runs.red_tree_copy(tree) as copy:
        built = Verdict()
        compiles(built, runs.on(copy), profile)
        if built.failed:
            result.take((BreakChecks.reproof_uncompiled(
                tuple(Selector(s) for s in moved),
                Detail("\n".join(m for st, _c, m in built.entries if st == "fail")[-600:])),))
            return
        probe = Verdict()
        test_state(probe, runs.on(copy), profile, table, "red", {s: located[s] for s in moved})
    proved = []
    for selector in moved:
        seen = tuple(f for f in findings_of(probe, "tests-red") if selector in f.said.value)
        timed_out = presence(any(f.state is FindingState.NOTE for f in seen))
        found = BreakChecks.reproof(Selector(selector), BreakChecks.verdict(seen), timed_out)
        result.take((found,))
        if found.state is FindingState.PASS:
            proved.append(selector)
    if proved:
        digests = runs.digests(story)
        runs.write_ledger(story, set(proved), located, {s: d for s, d in digests.items() if s not in proved})
        for selector in proved:
            runs.reproved(story, selector)


def judge_suite(result: Verdict, suite: typing.Any, required: bool, strict: bool = False) -> None:
    """A suite's run judged (`SuiteChecks.suite`); a test noted flaky is carried in the verdict."""
    judged = SuiteChecks.suite(suite, presence(required), presence(strict))
    result.take(judged.findings)
    result.flaky += [test.value for test in judged.flaky]


def suite_named(result: Verdict, before: int) -> None:
    """The entries a suite's run left since `before` reported under `suite` (a flaky test under its own name)."""
    result.entries[before:] = [(state, "suite" if name != "flaky" else name, message)
                               for state, name, message in result.entries[before:]]


def required_suites(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], story: str,
                    mapping: typing.Optional[Mapping], already: typing.Optional[WholeRuns] = None) -> None:
    """At build and tidy: the test commands the policy requires, run whole. A command the test-state check already
    ran whole is judged from that run — one process per command per gate, not two."""
    already = already or {}
    commands = runs.suite_commands()
    result.take(SuiteChecks.required(commands))
    required = {key.value for key in commands.required}
    seen = set()
    for key in [k for k in runs.test_keys() if k in required and profile.get(k)]:
        if profile[key] in seen:
            continue
        seen.add(profile[key])
        before = len(result.entries)
        if profile[key] in already:
            _key, code, output, ran = already[profile[key]]
            judge_suite(result, runs.suite(key, profile[key], story, mapping or {}, (code, output, ran),
                                           reused=" (the run the mapped tests were read from)"), True, True)
        else:
            judge_suite(result, runs.suite(key, profile[key], story, mapping or {}), True, True)
        suite_named(result, before)


def task_suites(result: Verdict, runs: StageRuns, profile: typing.Mapping[str, typing.Any], story: str,
                mapping: typing.Optional[Mapping]) -> None:
    """At a task's build and tidy gates: every test command the profile declares, run whole — nothing a test was
    written for, so everything the stories before delivered has to hold."""
    found = SuiteChecks.task(runs.suite_commands())
    result.take(found)
    if found:
        return
    seen = set()
    for key in [key for key in runs.test_keys() if profile.get(key)]:
        if profile[key] in seen:
            continue
        seen.add(profile[key])
        before = len(result.entries)
        judge_suite(result, runs.suite(key, profile[key], story, mapping or {}), True, True)
        suite_named(result, before)


def whole_suites(run: Run) -> typing.Tuple[str, ...]:
    """At build and tidy the policy's required test commands run whole anyway: that run is the evidence for the
    mapped tests as well, so those commands are not started a second time."""
    if not run.stage.suite:
        return ()
    required = set(re.split(r"[\s,]+", str(run.profile.get("required") or "").strip()))
    return tuple(k for k in run.runs_port.test_keys() if k in required and run.profile.get(k))


def adopt(result: Verdict, run: Run) -> None:
    """The adopt gate: an adopted story is delivered when every scenario maps to a test that exists and is green, a
    fresh judge passed it, and every test the adoption wrote itself turns red under its break — a minimal change to
    the production code, applied to a scratch copy, never to the tree."""
    refused = BreakChecks.adopted(run.story)
    result.take(refused)
    if refused:
        return
    runs: StageRuns = run.runs_port
    mapping, located = read_table(run)
    compiles(result, runs, run.profile)
    result.take(DesignChecks.invariants(run.story, run.contract, table_tests(mapping), run.evidence))
    # every rule's unit test is green beside the scenarios' tests: an adoption proves what holds, the rules included
    in_table = {s for sels in mapping.values() for s in sels}
    rules = {f"{element} rule {', '.join(map(str, numbers))}": [selector]
             for element, numbers, selector in runs.invariant_rows(run.story_id) or []
             if selector and SELECTOR_FORM.match(selector) and selector not in in_table}
    if rules and run.contract.value >= ADOPTED_RULES_CONTRACT.value:
        located = dict(located, **runs.locate(rules))
        mapping = dict(mapping, **rules)
    test_state(result, runs, run.profile, mapping, "green", located, run.story_id, guard=True,
               red_proof=(run.story, run.evidence))
    result.take((BreakChecks.adopt_judged(Detail(runs.judge_verdict(run.story_id))),))
    everything = str(run.profile.get("adopt.breakProof", "")).strip().lower() == "all"
    by_selector = {sel: key for key, sels in mapping.items() for sel in sels}
    written = runs.characterization(run.story_id, by_selector)
    wanted = sorted(by_selector) if everything else written
    extra = {sel for sel in wanted if sel not in located}
    if extra:
        located = dict(located, **runs.locate({OUTSIDE: sorted(extra)}))
    if wanted:
        with runs.scratch() as copied:
            for selector in wanted:
                break_proof(result, runs, run.profile, run.story_id, selector, by_selector.get(selector, OUTSIDE),
                            located, copied)
    else:
        result.take((BreakChecks.nothing_written(),))


def tested(stage: Stage) -> bool:
    return Trait.TESTED in stage.traits


def commanded(stage: Stage) -> bool:
    return bool(stage.commands)


@check("adopt", stages=("adopt",))
def _adopt(run: Run) -> None:
    adopt(run.result, run)


@check("tests", stages=tested, needs_process=True,
       unrun=lambda run: ["compiles", f"tests-{run.expected}"] + (["suite"] if run.stage.suite else []))
def _tests(run: Run) -> None:
    runs: StageRuns = run.runs_port
    compiles(run.result, runs, run.profile)
    if run.kind == "task":
        task_suites(run.result, runs, run.profile, run.story_id, run.mapping)
        return
    run.whole_runs = test_state(run.result, runs, run.profile, run.mapping, run.expected, run.located, run.story_id,
                                guard=run.kind in ("journey", "adopt"), whole_for=whole_suites(run))
    if run.stage.suite:
        required_suites(run.result, runs, run.profile, run.story_id, run.mapping, run.whole_runs)


@check("invariant-breaks", stages=("test",), needs_process=True, kinds=frozenset((StoryKind.STORY,)))
def _invariant_breaks(run: Run) -> None:
    if run.contract.value >= INVARIANT_BREAKS_CONTRACT.value:
        invariant_breaks(run.result, run.runs_port, run.profile, run.story_id, run.mapping)


@check("red-reproof", stages=("tidy",), needs_process=True, kinds=frozenset((StoryKind.STORY,)))
def _red_reproof(run: Run) -> None:
    reproof(run.result, run.runs_port, run.profile, run.story_id, run.mapping, run.located)


@check("commands", stages=commanded, needs_process=True,
       unrun=lambda run: [key for key in run.stage.commands if run.profile.get(key)])
def _commands(run: Run) -> None:
    """The gate must not *know* its checks, it looks them up: adding a capability is one line in the profile."""
    for key in run.stage.commands:
        command = run.profile.get(key)
        run.result.take((SuiteChecks.command(CheckName(key), run.runs_port.command(command)) if command
                         else SuiteChecks.missing(CheckName(key), CommandKey(key)),))
