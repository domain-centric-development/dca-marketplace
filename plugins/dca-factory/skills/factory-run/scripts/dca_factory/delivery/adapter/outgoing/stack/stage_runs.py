"""A gate's runs in a project tree, as files and processes: the mapped tests and the red ledger, the suites and
commands, a test's break on a scratch copy, the rules' proofs, a test re-proved on the red tree."""

from __future__ import annotations

import contextlib
import os
import typing

from ....domain.model.stage_story import CommandRun, RedLedger, SuiteCommands, SuiteRun, TestRun
from ..files.decision_record_files import answered_decisions
from ..files.design_files import read_invariant_rows
from ..files.journal_files import journal_append
from ..files.kept_files import read_red_digests, red_tree, red_tree_copy, tidy_moves, write_red_ledger
from ..files.run_marks import verdict_in, write_mark
from ..files.signals import journal_signal
from ..files.story_record import INVARIANT_BREAKS
from ..files.test_files import locate_tests
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .breaks import apply_break, break_copy, break_patch, break_path, characterization_tests, qualify_selector
from .commands import test_command_keys
from .suite_runs import command_run, suite_commands, suite_run, SuiteOwner
from .test_runs import red_ledger, run_tests, WholeRuns

Mapping = typing.Mapping[str, typing.Sequence[str]]
Located = typing.Mapping[str, str]


class StageRunFiles:
    """The runs of the project tree <cwd>, the run folder <runs>, the profile."""

    def __init__(self, cwd: str, runs: str, profile: typing.Mapping[str, typing.Any]) -> None:
        self._cwd = cwd
        self._runs = runs
        self._profile = profile

    def on(self, cwd: str) -> StageRunFiles:
        return StageRunFiles(cwd, self._runs, self._profile)

    def tests(self, mapping: Mapping, located: Located, whole_for: typing.Iterable[str]
              ) -> typing.Tuple[TestRun, WholeRuns]:
        return run_tests(self._profile, self._cwd, mapping, located, whole_for)

    def ledger(self, story: typing.Optional[str], red: bool, located: Located) -> RedLedger:
        return red_ledger(self._cwd, self._runs, story, red, located)

    def digests(self, story: typing.Optional[str]) -> typing.Dict[str, typing.Optional[str]]:
        return read_red_digests(self._runs, story or "")

    def write_ledger(self, story: typing.Optional[str], selectors: typing.Collection[str], located: Located,
                     kept: typing.Mapping[str, typing.Optional[str]]) -> None:
        write_red_ledger(self._runs, story, selectors, located, self._cwd, kept)

    def locate(self, mapping: Mapping) -> typing.Dict[str, str]:
        return locate_tests(self._cwd, mapping)[0] if mapping else {}

    def command(self, command: str) -> CommandRun:
        return command_run(self._cwd, command)

    def suite(self, key: str, command: str, story: typing.Optional[str], mapping: Mapping,
              already: typing.Optional[typing.Tuple[int, str, typing.Dict[typing.Tuple[str, str], str]]] = None,
              reused: str = "") -> SuiteRun:
        owner = SuiteOwner(self._runs, story, mapping) if story else None
        return suite_run(self._cwd, self._profile, key, command, owner, already, reused)

    def suite_commands(self) -> SuiteCommands:
        return suite_commands(self._profile)

    def test_keys(self) -> typing.List[str]:
        return test_command_keys(self._profile)

    def patch(self, story: str, selector: str) -> typing.Optional[str]:
        return break_patch(self._runs, story, selector)

    def patch_place(self, story: str, selector: str) -> str:
        return os.path.relpath(break_path(self._runs, story, selector), self._cwd)

    def scratch(self) -> typing.ContextManager[typing.Tuple[str, str]]:
        return break_copy(self._cwd)

    def apply(self, copy: str, scratch: str, patch: str, reverse: bool = False) -> typing.Tuple[int, str]:
        return apply_break(copy, scratch, patch, reverse)

    def invariant_rows(self, story: str) -> typing.Optional[typing.List[typing.Tuple[str, typing.List[int], str]]]:
        path = os.path.join(self._runs, story, "tests.md")
        return read_invariant_rows(read_text(path)) if os.path.isfile(path) else None

    def rule_proofs(self, story: str, rows: typing.Sequence[typing.Tuple[str, typing.List[int], str, str]]) -> None:
        write_mark(self._runs, story, INVARIANT_BREAKS, "\n".join(
            f"{e}\t{','.join(map(str, n))}\t{sel}\t{verdict}" for e, n, sel, verdict in rows))
        journal_signal(self._runs, story, "rules", [("rule", sel, dict(element=e, rules=",".join(map(str, n)),
                                                                       verdict=verdict))
                                                    for e, n, sel, verdict in rows],
                       named=sum(len(n) for _e, n, _s, _v in rows))

    def answered_tests(self, story: str) -> typing.List[str]:
        return answered_decisions(self._cwd, story, "test")

    def tidy_moves(self, story: str, located: Located) -> typing.List[str]:
        return tidy_moves(self._cwd, self._runs, story, dict(located))

    def red_tree(self, story: str) -> typing.Optional[str]:
        return red_tree(self._runs, story)

    def red_tree_copy(self, tree: str) -> typing.ContextManager[str]:
        return red_tree_copy(self._cwd, self._runs, tree)

    def reproved(self, story: str, selector: str) -> None:
        with contextlib.suppress(OSError):
            journal_append(self._runs, story, "red-reproved", selector, "by=tidy")

    def characterization(self, story: str, by_selector: typing.Mapping[str, str]) -> typing.List[str]:
        return [qualify_selector(sel, by_selector, self._cwd) for sel in characterization_tests(self._runs, story)]

    def judge_verdict(self, story: str) -> str:
        path = os.path.join(self._runs, story, "judge.md")
        return verdict_in(read_text(path)) or "" if os.path.isfile(path) else ""
