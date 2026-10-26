"""What a run of a story's mapped tests proves: red before the code exists, green after — and only for a test that
was seen red, ran by name, and is the version that was."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService, Value
from ..model.stage_story import (
    Evidence, Expectation, Presence, RedLedger, RunEnd, RunState, ScenarioKey, Selector, TestOutcome, TestRun)
from ..model.verdict import CheckName, Finding, FindingState, Said


class BreakProof(Value):
    """A green test changed after an earlier pass's build met it: a break of the code shows whether its new
    assertion bites — the gate's run applies it to a copy and holds the test to the outcome."""

    key: ScenarioKey
    selector: Selector


class TestsJudged(Value):
    """The findings and break proofs in order, and the tests that count as red now — the red ledger's next entries."""

    items: typing.Tuple[typing.Union[Finding, BreakProof], ...]
    now_red: typing.FrozenSet[Selector]


def timeout_said(selector: Selector) -> Said:
    return Said(f"{selector.value} is red on a timeout, not on an assertion — an action waited for something that is "
                f"not there. Red is red, but it says nothing about what is missing: the first step that can be "
                f"missing should be an expectation (`expect(locator).toBeVisible()` before the click or fill), so "
                f"the failure names it.")


#: The check that holds every mapped test red at the test stage.
RED_CHECK = CheckName("tests-red")
#: What it says of a test it lets through green — on a decision, or one an earlier pass's build met.
GREEN_NOW = "is green now"


class TestVerdicts(DomainService):
    """Expected red: every mapped test fails. Green: all pass. A guard — a journey over delivered stories — is green
    without ever having been red: its steps exist before it is written."""

    @staticmethod
    def let_through_green(check: CheckName, state: FindingState, said: Said) -> Presence:
        """Whether a finding of the test gate says a test went through green — then the tree is past the red state,
        and the red tree an earlier pass recorded stays."""
        return Presence.PRESENT if check == RED_CHECK and state is FindingState.PASS and GREEN_NOW in said.value \
            else Presence.ABSENT

    @staticmethod
    def judge(expected: Expectation, guard: Presence, run: TestRun, ledger: RedLedger) -> TestsJudged:
        name = CheckName(f"tests-{expected.value}")
        red = expected is Expectation.RED
        if run.command is Presence.ABSENT:
            return TestsJudged((name.skip(Said("no `e2eTest:` or `test:` command in the stack profile")),),
                               frozenset())
        items: typing.List[typing.Union[Finding, BreakProof]] = []
        now_red: typing.Set[Selector] = set()
        timed_out: typing.List[Selector] = []
        for item in run.items:
            if isinstance(item, RunEnd):
                if timed_out and item.shared is Presence.PRESENT:
                    # One output for the run: which of its red tests hit the timeout is not readable from it.
                    items.append(name.note(Said(
                        f"`{item.invocation.value}`: red on a timeout, not on an assertion, somewhere among "
                        f"{', '.join(s.value for s in timed_out)} — an action waited for something that is not "
                        f"there; the first step that can be missing should be an expectation "
                        f"(`expect(locator).toBeVisible()` before the click or fill), so the failure names it.")))
                else:
                    items += [name.note(timeout_said(s)) for s in timed_out]
                timed_out = []
                continue
            test = item
            selector, key = test.selector.value, test.key.value
            if test.state is RunState.NO_FILE:
                items.append(name.fail(Said(
                    f"{selector}: `filterFormat` selects by `{{file}}`, but no source file was located for it — "
                    f"nothing to run for {key!r}.")))
                continue
            if test.state is RunState.UNCOVERED:
                # Running it with some other command proves nothing in either direction: a runner that matched no
                # test exits 0 on one stack (looks green) and non-zero on another (looks red).
                where = test.place.value if test.place else "?"
                items.append(name.fail(Said(
                    f"{selector} lives in {where}, which no declared test command covers. Declare that source set in "
                    f"the stack profile (`test.<name>: <command>`), or state the scope of a command that already runs "
                    f"it (`covers.<key>: <paths>` or `covers.<key>: **`); a run with any other command would match no "
                    f"test, and that exits 0 on one runner and non-zero on another — neither is evidence about "
                    f"{key!r}.")))
                continue
            if test.state is RunState.NOT_DISCRIMINATED:
                items.append(name.fail(Said(
                    f"{selector}: `{test.invocation.value}` answers a selector that cannot exist the same way (exit "
                    f"{test.code.value}), so it never ran this test — no evidence about {key!r}:\n"
                    f"{test.output.value}")))
                continue
            if test.alone is not None:
                items.append(name.note(Said(
                    f"{selector}: absent from the report of `{test.invocation.value}`, run alone "
                    f"(`{test.alone.value}`) — a runner that drops a joined filter costs one process per selector "
                    f"here")))
            if test.state is RunState.NOT_REPORTED:
                detail = f" — {test.how.value}" if test.how.value else \
                    f" ({test.cases.value} case(s) in the report(s) written by this run)"
                items.append(name.fail(Said(
                    f"{selector}: no test report from this run shows it ran{detail}. Let the runner write one (JUnit "
                    f"XML is the default on the JVM; .NET needs `--logger trx`), point `testReport:` at it, give the "
                    f"test a name the report carries, or accept the weaker check with `testEvidence: exit-code`:\n"
                    f"{test.output.value}")))
                continue
            if test.state is RunState.SKIPPED:
                items.append(name.fail(Said(f"{selector} was skipped rather than run, so it says nothing about "
                                            f"{key!r}.")))
                continue
            if test.evidence is Evidence.EXIT_CODE:
                items.append(name.skip(Said(
                    f"{selector}: `testEvidence: exit-code` — the verdict rests on the exit code, not on a report of "
                    f"what ran. A runner that exits like a failing test without running one is indistinguishable "
                    f"here.")))
            passed = test.state is RunState.PASSED
            items += TestVerdicts._verdict(expected, guard, test, ledger, now_red)
            if red and not passed and test.timeout is Presence.PRESENT:
                if test.evidence is Evidence.EXIT_CODE:
                    items.append(name.note(timeout_said(test.selector)))
                else:
                    timed_out.append(test.selector)
        return TestsJudged(tuple(items), frozenset(now_red))

    @staticmethod
    def _verdict(expected: Expectation, guard: Presence, test: TestOutcome, ledger: RedLedger,
                 now_red: typing.Set[Selector]) -> typing.List[typing.Union[Finding, BreakProof]]:
        """The test's verdict against what the ledger and the stage expect — unchanged by how it ran."""
        changed_on = ", ".join(r.value for r in ledger.changed_on)
        green, red = CheckName("tests-green"), RED_CHECK
        selector, key = test.selector.value, test.key.value
        passed = test.state is RunState.PASSED
        if not passed:
            now_red.add(test.selector)
        if expected is Expectation.GREEN and passed and guard is Presence.PRESENT:
            return [green.ok(Said(f"{selector} passes — a journey guards what is delivered ({key})"))]
        if expected is Expectation.GREEN and passed and ledger.present is Presence.ABSENT:
            # No test stage ran in this checkout — the run artefacts may simply not be committed. Say that the
            # evidence is missing instead of inventing either verdict.
            return [green.skip(Said(f"{selector} is green, but no `{ledger.name.value}` from a test stage is present "
                                    f"here, so nothing proves it ever failed ({key!r})."))]
        if expected is Expectation.GREEN and passed and test.selector not in ledger.was_red:
            # Never seen red: a runner that matched nothing exits 0 exactly like a passing test, so "green" alone is
            # no evidence that this test ran at all.
            return [green.fail(Said(
                f"{selector} passes now but was never recorded red by the test stage ({key!r}) — a test that never "
                f"failed proves nothing, and a run that matched no test passes too. Run `--stage test` before the "
                f"build stage."))]
        if expected is Expectation.RED and passed and test.selector in ledger.was_red and changed_on:
            now_red.add(test.selector)
            return [red.ok(Said(f"{selector} {GREEN_NOW} and was recorded red before; its expectation changed on "
                                f"decision {changed_on} ({key})"))]
        if expected is Expectation.RED and passed and test.selector in ledger.was_red \
                and ledger.built_before is Presence.PRESENT:
            if test.selector in ledger.moved:
                # Changed after its build met it — the judge sent it back as asserting too little. It is green and
                # can never be seen red again: one change to the code that turns it red shows that the new assertion
                # bites.
                return [BreakProof(test.key, test.selector)]
            now_red.add(test.selector)
            return [red.ok(Said(f"{selector} {GREEN_NOW} and was recorded red in an earlier pass of this story, "
                                f"whose build met it ({key})"))]
        if expected is Expectation.RED and passed:
            return [red.fail(Said(
                f"{selector} passes before the build stage — a test that is green before the code exists proves "
                f"nothing about {key!r}. Either the test asserts nothing new (the test stage fixes it), or {key!r} "
                f"describes behaviour the system already has — then the criterion does not belong in the story, and "
                f"that is the story author's call, not a stage's."))]
        if expected is Expectation.GREEN and not passed:
            return [green.fail(Said(f"{selector} fails, so criterion {key!r} is not met:\n{test.output.value}"))]
        name = CheckName(f"tests-{expected.value}")
        evidence = f", {test.how.value}" if test.how.value else ""
        command = test.command.value if test.command else "?"
        return [name.ok(Said(f"{selector} is {'green' if passed else 'red'} ({key}, via `{command}:`{evidence})"))]
