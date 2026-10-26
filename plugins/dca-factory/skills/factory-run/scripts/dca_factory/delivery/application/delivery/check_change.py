"""Check a change outside a story: the profile's checks over one tree — a direct edit, a commit (the index, refused
where the working tree differs from it) and CI get one verdict."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.stage_story import CommandKey, Count, Presence
from ...domain.model.story_state import Detail
from ...domain.model.verdict import CheckName, FindingState
from ...domain.service.change_checks import CHANGE_CHECKS, ChangeChecks
from ..shared.change_index import ChangeIndex
from ..shared.stage_runs import StageRuns
from .check_stage import Verdict
from .process_checks import judge_suite


def names(text: typing.Any) -> typing.List[str]:
    """The keys a profile line or a flag names, comma- or space-separated."""
    return [part for part in str(text or "").replace(",", " ").split() if part]


@dataclasses.dataclass(frozen=True)
class CheckChangeCommand:
    """`staged`: the commit's index rather than the working tree; `only`: the checks a person named."""

    staged: bool
    only: typing.Optional[str]


class CheckChangeInputPort(UseCase[CheckChangeCommand, Verdict], typing.Protocol):
    """Check a change outside a story."""


class CheckChangeUseCase:
    """The profile declares the commands; its `required:` line declares which of them must hold. Without that line
    the check reports what it ran and what it skipped, and fails only on a red command. A commit of the backlog alone
    runs what `checks.backlog` names and nothing more."""

    def __init__(self, profile: typing.Mapping[str, typing.Any], index: ChangeIndex, runs: StageRuns) -> None:
        self._profile = profile
        self._index = index
        self._runs = runs

    def execute(self, command: CheckChangeCommand) -> Verdict:
        result, profile = Verdict(), self._profile
        required = set(names(profile.get("required")))
        strict = Presence.PRESENT if required else Presence.ABSENT
        result.take(ChangeChecks.policy(frozenset(CommandKey(r) for r in required)))
        tree = None
        paths = self._index.backlog_paths() if command.staged and not names(command.only) else None
        if command.staged:
            if paths and not names(profile.get("checks.backlog")):
                result.take((ChangeChecks.backlog_alone(),))
            else:
                index = self._index.snapshot()
                found = ChangeChecks.snapshot(index)
                result.take((found,))
                if found.state is not FindingState.PASS:
                    return result
                tree = index.tree.value
            self._index.detach()
        else:
            head = self._index.head()
            result.take((ChangeChecks.working_tree(Detail(head) if head is not None else None),))
        scope = names(command.only) or list(CHANGE_CHECKS)
        declared = self._runs.test_keys()
        test_keys = declared + sorted(r for r in required if (r == "e2eTest" or r.startswith("test."))
                                      and r not in declared)
        # A commit of the backlog alone — stories, decisions, findings, the pipeline's protocol — changes no code: it
        # runs what `checks.backlog` names (a project whose tests read the backlog names them), by each check's or
        # test command's own key, and nothing more. An explicit `--checks` scope is the person's and wins.
        test_scope = None
        if paths:
            named = names(profile.get("checks.backlog"))
            result.take(ChangeChecks.backlog_scope(tuple(CommandKey(n) for n in named),
                                                   tuple(CommandKey(k) for k in test_keys), Count(len(paths))))
            test_scope = {n for n in named if n in test_keys}
            scope = [n for n in named if n in CHANGE_CHECKS and n != "test"] + (["test"] if test_scope else [])
        for check in CHANGE_CHECKS:
            if check == "test":
                self._tests(result, scope, test_keys, test_scope, required)
                continue
            must = Presence.PRESENT if check in required else Presence.ABSENT
            if check not in scope:
                result.take((ChangeChecks.test_out_of_scope(CommandKey(check), must),))
                continue
            line = profile.get(check)
            if not line:
                result.take((ChangeChecks.missing(CheckName(check), CommandKey(check), must),))
                continue
            result.take((ChangeChecks.command(CheckName(check), self._runs.command(line), must, strict),))
        if tree:
            after = self._index.tree()
            if after != tree:
                result.take((ChangeChecks.index_changed(Detail(tree), Detail(after)),))
        return result

    def _tests(self, result: Verdict, scope: typing.List[str], test_keys: typing.List[str],
               test_scope: typing.Optional[typing.Set[str]], required: typing.Set[str]) -> None:
        required_tests = [k for k in test_keys if k in required]
        if "test" not in scope:
            result.take((ChangeChecks.out_of_scope(CheckName("test"), tuple(CommandKey(k) for k in required_tests)),))
            return
        commands: typing.Dict[str, typing.List[str]] = {}
        for key in test_keys:
            if test_scope is not None and key not in test_scope:
                result.take((ChangeChecks.test_out_of_scope(
                    CommandKey(key), Presence.PRESENT if key in required else Presence.ABSENT),))
                continue
            if self._profile.get(key):
                commands.setdefault(self._profile[key], []).append(key)
            elif key in required:
                result.take((ChangeChecks.missing_test(CommandKey(key)),))
        if not commands and not required_tests:
            result.take((ChangeChecks.no_test(),))
        for line, keys in commands.items():
            judge_suite(result, self._runs.suite("/".join(keys), line, None, {}),
                        any(k in required for k in keys), bool(required))
