"""A story's mapped tests run as the profile declares them: one process per test command, each test's verdict read
from that run's reports by name — and the red ledger the verdicts are held to."""

from __future__ import annotations

import contextlib
import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..files.hand_over_patterns import SELECTOR
from ..pipeline.stage_rows import STAGE_FILES
from ....domain.model.decision_record import RecordId
from ....domain.model.stage_story import (
    CommandKey, Count, Evidence, Place, Presence, RedLedger, RunEnd, RunState, ScenarioKey, Selector, TestOutcome,
    TestRun)
from ....domain.model.story_state import Detail
from ..files.decision_record_files import acceptance_records, answered_decisions
from ..files.kept_files import read_red_digests, red_ledger_path
from ..files.story_layout import file_digest
from .commands import command_for, discriminates, joined_filter, recorded_run, red_on_timeout, run, tail
from .test_reports import display_name_of, fill, normalise, outcome_for
from ....domain.model.decision_record import DecisionState, Given
from ....domain.service.acceptance_rules import AcceptanceRules

Located = typing.Mapping[str, str]
#: {command: (key, code, output, ran)} of a command run whole
WholeRuns = typing.Dict[str, typing.Tuple[str, int, str, typing.Dict[typing.Tuple[str, str], str]]]


def run_tests(profile: typing.Mapping[str, typing.Any], cwd: str, mapping: typing.Mapping[str, typing.Sequence[str]],
              located: Located, whole_for: typing.Iterable[str] = ()) -> typing.Tuple[TestRun, WholeRuns]:
    """Every mapped test run, in the order of the commands that cover them.

    One process per test command, not per selector: every selector a command covers goes into one invocation, and
    each selector's outcome is read from that run's reports by name. A command in `whole_for` (the policy's
    `required:` commands at the build and tidy gates) runs whole instead, and the run is returned, so the suite check
    reads it rather than running the same command again. `testEvidence: exit-code` keeps one process per selector:
    it has no report to read a name from."""
    fallback = profile.get("e2eTest") or profile.get("test")
    flag = profile.get("filterFlag", "")
    fmt = profile.get("filterFormat", "{class}.{method}")
    whole = set(whole_for or ())
    whole_runs: WholeRuns = {}
    if not fallback:
        return TestRun(Presence.ABSENT, ()), whole_runs
    by_report = profile.get("testEvidence", "").strip() != "exit-code"
    items: typing.List[typing.Union[TestOutcome, RunEnd]] = []

    def outcome(key: str, selector: str, test_path: typing.Optional[str], command_key: typing.Optional[str],
                state: RunState, evidence: Evidence = Evidence.REPORT, how: str = "", invocation: str = "",
                alone: typing.Optional[str] = None, code: int = 0, output: str = "", cases: int = 0,
                timeout: bool = False) -> TestOutcome:
        return TestOutcome(ScenarioKey(key), Selector(selector), Place(test_path) if test_path else None,
                           CommandKey(command_key) if command_key else None, state, evidence, Detail(how),
                           Detail(invocation), Detail(alone) if alone else None, Count(code), Detail(tail(output)),
                           Count(cases), Presence.PRESENT if timeout else Presence.ABSENT)

    # 1. Every selector resolves to the command that covers it — or to a configuration fail — before anything runs.
    #    Grouped by command, one process then carries every selector it covers.
    groups: typing.Dict[str, typing.List[typing.Tuple[str, str, str, str, typing.Optional[str], str, str]]] = {}
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            match = SELECTOR.match(selector)
            assert match is not None, selector
            cls, method = match.groups()
            test_path = located.get(selector)
            if "{file}" in fmt and not test_path:
                # The filter names the file, and no file was found for this selector — running the placeholder
                # literally would select nothing, and that exits 0 on some runners.
                items.append(outcome(key, selector, None, None, RunState.NO_FILE))
                continue
            pattern = fill(fmt, cls, method, test_path)
            command_key, command = command_for(profile, test_path) if test_path else (None, None)
            if not command and test_path:
                items.append(outcome(key, selector, test_path, None, RunState.UNCOVERED))
                continue
            if not command:
                command_key, command = "e2eTest" if profile.get("e2eTest") else "test", fallback
            groups.setdefault(command, []).append((key, selector, cls, method, test_path, command_key or "", pattern))

    # 2. One process per command. Where the policy runs the command whole at this gate anyway, the whole run is the
    #    evidence for its selectors too; elsewhere every selector goes into one filtered run.
    control: typing.Dict[str, typing.Tuple[int, str]] = {}
    for command, group in groups.items():
        command_key = group[0][5]
        patterns = list(dict.fromkeys(item[6] for item in group))
        if not by_report:
            # `testEvidence: exit-code`: the exit code is all there is, and it belongs to one selector.
            for key, selector, _cls, _method, test_path, command_key, pattern in group:
                invocation = f'{command} {flag} "{pattern}"'.strip()
                code, output = run(invocation, cwd)
                control_code, control_output = discriminates(command, flag, fmt, cwd, control)
                if code == control_code and normalise(output, cwd) == control_output:
                    items.append(outcome(key, selector, test_path, command_key, RunState.NOT_DISCRIMINATED,
                                         invocation=invocation, code=code, output=output))
                    continue
                items.append(outcome(key, selector, test_path, command_key,
                                     RunState.PASSED if code == 0 else RunState.FAILED, Evidence.EXIT_CODE,
                                     invocation=invocation, code=code, output=output,
                                     timeout=code != 0 and red_on_timeout(output)))
            continue
        runs_whole = command_key in whole
        invocation = command if runs_whole else f"{command} {joined_filter(profile, flag, patterns)}".strip()
        code, output, ran, reused = recorded_run(invocation, cwd, profile, with_reports=True)
        if runs_whole:
            whole_runs[command] = (command_key, code, output, ran)
        shared = runs_whole or len(patterns) > 1
        for key, selector, cls, method, test_path, command_key, pattern in group:
            display = display_name_of(test_path, method)
            state, how = outcome_for(ran, cls, method, display)
            item_output, alone = output, None
            if state is None and shared:
                # Not in the shared run's report. Before that fails the selector it runs alone, once: a runner that
                # honours one filter and drops the second, or a whole run that skipped a source set, must not fail a
                # test that a run of its own would show.
                alone_invocation = f'{command} {flag} "{pattern}"'.strip()
                _code_alone, item_output, ran_alone, reused = recorded_run(alone_invocation, cwd, profile,
                                                                           with_reports=True)
                state, how = outcome_for(ran_alone, cls, method, display)
                if state is not None:
                    alone = alone_invocation
            if state is None:
                items.append(outcome(key, selector, test_path, command_key, RunState.NOT_REPORTED, how=how or "",
                                     invocation=invocation, output=item_output, cases=len(ran)))
                continue
            if state == "skipped":
                items.append(outcome(key, selector, test_path, command_key, RunState.SKIPPED, invocation=invocation,
                                     alone=alone))
                continue
            # The report decides, not the exit code: a build can fail for reasons beside this test, and a runner can
            # exit 0 with a failure recorded.
            passed = state == "passed"
            items.append(outcome(key, selector, test_path, command_key,
                                 RunState.PASSED if passed else RunState.FAILED, how=f"report {how}{reused}",
                                 invocation=invocation, alone=alone, output=item_output,
                                 timeout=not passed and red_on_timeout(item_output)))
        items.append(RunEnd(Detail(invocation), Presence.PRESENT if shared else Presence.ABSENT))
    return TestRun(Presence.PRESENT, tuple(items)), whole_runs


def red_ledger(cwd: str, runs: typing.Optional[str], story: typing.Optional[str], red: bool,
               located: Located) -> RedLedger:
    """The red ledger as the run's verdicts read it.

    An expectation that changes on a human's decision: the test was recorded red before the code existed, the
    decision changed what it expects, and the code now meets it. A story that runs again for a human's correction
    keeps the criteria it had already met: their tests were red once, for this very story. A story planned again
    keeps the criteria its earlier pass already built: their tests were seen red for this story, and a build made
    them green."""
    ledger = red_ledger_path(runs or "", story or "")
    digests = read_red_digests(runs or "", story or "")
    changed_on: typing.List[str] = []
    if red:
        changed_on = answered_decisions(cwd, story or "", "test")
        with contextlib.suppress(GateError):
            changed_on += [rid for rid, _f, state, answer, _b in acceptance_records(cwd, story or "")
                           if AcceptanceRules.corrects(DecisionState(state), Given(str(answer.get("answer", ""))))
                           is Presence.PRESENT]
    built = bool(runs and story) and os.path.isfile(os.path.join(runs or "", story or "", STAGE_FILES["build"]))
    moved = frozenset(Selector(selector) for selector, recorded in digests.items()
                      if recorded and located.get(selector) and os.path.isfile(os.path.join(cwd, located[selector]))
                      and file_digest(os.path.join(cwd, located[selector])) != recorded)
    return RedLedger(Presence.PRESENT if ledger and os.path.isfile(ledger) else Presence.ABSENT,
                     Detail(os.path.basename(ledger) if ledger else ".tests-red"),
                     frozenset(Selector(s) for s in digests), tuple(RecordId(r) for r in changed_on),
                     Presence.PRESENT if built else Presence.ABSENT, moved)
