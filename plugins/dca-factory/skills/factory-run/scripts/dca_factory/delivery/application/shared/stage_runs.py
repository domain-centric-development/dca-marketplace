"""What a gate runs in a project — the mapped tests, the suites and commands, a test's break on a scratch copy — and
what it keeps of the runs: the red ledger, the rules' proofs, a re-proved test."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.stage_story import CommandRun, RedLedger, SuiteCommands, SuiteRun, TestRun

Mapping = typing.Mapping[str, typing.Sequence[str]]
Located = typing.Mapping[str, str]
#: {command: (key, code, output, ran)} of a command run whole
WholeRuns = typing.Dict[str, typing.Tuple[str, int, str, typing.Dict[typing.Tuple[str, str], str]]]
Rows = typing.List[typing.Tuple[str, typing.List[int], str]]


class StageRuns(OutputPort, typing.Protocol):
    """The runs of one project tree — the working tree, or a scratch copy (`on`)."""

    def on(self, cwd: str) -> StageRuns:
        """The same runs over another tree: a scratch copy."""
        ...

    def tests(self, mapping: Mapping, located: Located, whole_for: typing.Iterable[str]
              ) -> typing.Tuple[TestRun, WholeRuns]:
        ...

    def ledger(self, story: typing.Optional[str], red: bool, located: Located) -> RedLedger:
        ...

    def digests(self, story: typing.Optional[str]) -> typing.Dict[str, typing.Optional[str]]:
        """The red ledger's tests and the digest of the version each was seen red."""
        ...

    def write_ledger(self, story: typing.Optional[str], selectors: typing.Collection[str], located: Located,
                     kept: typing.Mapping[str, typing.Optional[str]]) -> None:
        ...

    def locate(self, mapping: Mapping) -> typing.Dict[str, str]:
        ...

    def command(self, command: str) -> CommandRun:
        ...

    def suite(self, key: str, command: str, story: typing.Optional[str], mapping: Mapping,
              already: typing.Optional[typing.Tuple[int, str, typing.Dict[typing.Tuple[str, str], str]]] = None,
              reused: str = "") -> SuiteRun:
        """A test command run whole for the story (`story` None: for nobody's change) — or the run already made."""
        ...

    def suite_commands(self) -> SuiteCommands:
        ...

    def test_keys(self) -> typing.List[str]:
        """Every command key of the profile that runs tests, most specific first."""
        ...

    def patch(self, story: str, selector: str) -> typing.Optional[str]:
        """The break a test has, None where it has none."""
        ...

    def patch_place(self, story: str, selector: str) -> str:
        """Where a test's break belongs, as the gate names it."""
        ...

    def scratch(self) -> typing.ContextManager[typing.Tuple[str, str]]:
        """One scratch copy of the project for the breaks of a gate run: (copy, scratch folder)."""
        ...

    def apply(self, copy: str, scratch: str, patch: str, reverse: bool = False) -> typing.Tuple[int, str]:
        ...

    def invariant_rows(self, story: str) -> typing.Optional[Rows]:
        """The tests' `gate:invariants` table — None where it has none."""
        ...

    def rule_proofs(self, story: str, rows: typing.Sequence[typing.Tuple[str, typing.List[int], str, str]]) -> None:
        """How each rule's test was shown to guard it, kept in the evidence and the journal."""
        ...

    def answered_tests(self, story: str) -> typing.List[str]:
        """The answered decisions about tests."""
        ...

    def tidy_moves(self, story: str, located: Located) -> typing.List[str]:
        ...

    def red_tree(self, story: str) -> typing.Optional[str]:
        ...

    def red_tree_copy(self, tree: str) -> typing.ContextManager[str]:
        ...

    def reproved(self, story: str, selector: str) -> None:
        ...

    def characterization(self, story: str, by_selector: typing.Mapping[str, str]) -> typing.List[str]:
        """The tests the adoption wrote itself, named as the reports name them."""
        ...

    def judge_verdict(self, story: str) -> str:
        ...
