"""A test command run whole for a story: the tests that are the story's own, and a red test outside them run again
alone, once."""

from __future__ import annotations

import os
import re
import subprocess
import typing

from ..files.hand_over_patterns import SELECTOR
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, runs_top
from ....domain.model.stage_story import CommandKey, CommandRun, Count, Presence, Retried, SuiteCommands, SuiteRun
from ....domain.service.suite_checks import FLAKY_LIMIT, SuiteChecks
from ....domain.model.story_state import Detail
from ..files.delivery_files import SKIP_DIRS, TEST_FILE
from ..files.design_files import locate_selector
from ..files.kept_files import TESTS_BASELINE
from .commands import recorded_run, tail, test_command_keys
from .test_reports import fill, outcome_for

Profile = typing.Mapping[str, typing.Any]
Ran = typing.Dict[typing.Tuple[str, str], str]



class SuiteOwner(typing.NamedTuple):
    """Whose change a whole suite run judges: the story's run folder, id and criterion-to-test table."""
    runs: str
    story_id: str
    mapping: typing.Mapping[str, typing.Sequence[str]]


def story_test_files(cwd: str, owner: SuiteOwner) -> typing.Optional[typing.List[str]]:
    """The test files the story wrote or changed — not in its baseline, or another blob than there — or None without a
    baseline: then which tests are the story's cannot be told, and none is run again."""
    path = os.path.join(evidence_dir(owner.runs, owner.story_id), TESTS_BASELINE)
    if not os.path.isfile(path):
        return None
    before: typing.Dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "  " in line:
            blob, rel = line.split("  ", 1)
            before[rel] = blob
    files = test_files(cwd)
    if not files:
        return []
    try:
        completed = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=cwd, input="\n".join(files) + "\n",
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    blobs = completed.stdout.split()
    if completed.returncode or len(blobs) != len(files):
        return None
    return [rel for rel, blob in zip(files, blobs) if before.get(rel) != blob]


def story_owns(cwd: str, owner: SuiteOwner, own_files: typing.Sequence[str], cls: str, method: str) -> bool:
    """Whether a reported test is the story's: named in its table, or a class of a test file it wrote or changed —
    by the file's name or by a declaration in it. When in doubt it is the story's: its red proof must stay exact."""
    for selectors in (owner.mapping or {}).values():
        for selector in selectors:
            match = SELECTOR.match(selector)
            if match and match.group(2) == method and (
                    match.group(1) == cls or cls.endswith("." + match.group(1)) or match.group(1).endswith("." + cls)):
                return True
    names = [n for n in re.split(r"[.$+/:]", cls) if n][-2:]
    for rel in own_files:
        stem = os.path.splitext(os.path.basename(rel))[0]
        if stem in names:
            return True
        text = read_text(os.path.join(cwd, rel)) if os.path.isfile(os.path.join(cwd, rel)) else ""
        if names and re.search(rf"\b{re.escape(names[-1])}\b", text):
            return True
    return False


def alone_invocation(cwd: str, profile: Profile, command: str, cls: str, method: str) -> typing.Optional[str]:
    """The profile's way to run one test of `command` — `<command> <filterFlag> "<filterFormat>"` — or None where the
    profile names none (no filter, or the exit code as the only evidence): then nothing is run again."""
    if str(profile.get("testEvidence", "")).strip() == "exit-code":
        return None
    flag, fmt = profile.get("filterFlag", ""), profile.get("filterFormat", "")
    if not flag and not fmt:
        return None
    fmt = fmt or "{class}.{method}"
    test_path = None
    if "{file}" in fmt:
        located = locate_selector(cwd, f"{cls}#{method}") if SELECTOR.match(f"{cls}#{method}") else None
        if not located:
            return None
        test_path = os.path.relpath(located, cwd).replace(os.sep, "/")
    return f'{command} {flag} "{fill(fmt, cls, method, test_path)}"'.strip()


def test_files(cwd: str) -> typing.List[str]:
    found = []
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith("."))
        for name in sorted(files):
            if TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


def retry_outside(cwd: str, profile: Profile, command: str, code: int, ran: Ran, owner: typing.Optional[SuiteOwner]
                  ) -> typing.Tuple[int, Ran, typing.List[Retried], typing.List[Retried]]:
    """(code, ran, flaky, still) after the red tests outside the story ran again, each alone and once (WP-113).

    Only when every red test is outside the story and the profile can select one: a red test of the story's own stands
    as it is. Green alone, the test is flaky and the run counts as green; red again, the run stays red."""
    if owner is None:
        return code, ran, [], []
    failed = sorted(key for key, outcome in ran.items() if outcome == "failed")
    if not failed:
        return code, ran, [], []
    own_files = story_test_files(cwd, owner) if len(failed) <= FLAKY_LIMIT.value else None
    # A story whose own tests cannot be told apart counts every red test as its own.
    own = own_files is None or any(story_owns(cwd, owner, own_files, cls, method) for cls, method in failed)
    if SuiteChecks.retries(Count(len(failed)), Presence.PRESENT if own else Presence.ABSENT) is Presence.ABSENT:
        return code, ran, [], []
    flaky: typing.List[typing.Tuple[str, str, str]] = []
    still: typing.List[typing.Tuple[str, str, str]] = []
    for cls, method in failed:
        alone = alone_invocation(cwd, profile, command, cls, method)
        if not alone:
            return code, ran, [], []
        _code, _output, ran_alone, _reused = recorded_run(alone, cwd, profile, with_reports=True)
        outcome, _how = outcome_for(ran_alone, cls, method)
        (flaky if outcome == "passed" else still).append((cls, method, alone))
    if still:
        return code, ran, [], [Retried(Detail(f"{c}#{m}"), Detail(a)) for c, m, a in still]
    ran = dict(ran)
    for cls, method, _alone in flaky:
        ran[(cls, method)] = "passed"
    return 0, ran, [Retried(Detail(f"{c}#{m}"), Detail(a)) for c, m, a in flaky], []


def suite_run(cwd: str, profile: Profile, key: str, command: str, owner: typing.Optional[SuiteOwner] = None,
              already: typing.Optional[typing.Tuple[int, str, Ran]] = None, reused: str = "") -> SuiteRun:
    """The test command run whole — or the run the mapped tests were read from (`already`) — with a red test outside
    the story run again alone, once."""
    if already is None:
        code, output, ran, reused = recorded_run(command, cwd, profile, with_reports=True)
    else:
        code, output, ran = already
    code, ran, flaky, still = retry_outside(cwd, profile, command, code, ran, owner)
    return SuiteRun(Detail(key), CommandRun(Detail(command), Count(code), Detail(tail(output)), Detail(reused)),
                    Count(sum(1 for outcome in ran.values() if outcome != "skipped")),
                    Count(sum(1 for outcome in ran.values() if outcome == "failed")), tuple(flaky), tuple(still),
                    Presence.PRESENT if profile.get("testEvidence") == "exit-code" else Presence.ABSENT)


def command_run(cwd: str, command: str) -> CommandRun:
    """A profile command run — or the runner's record of it on this tree."""
    code, output, _ran, reused = recorded_run(command, cwd)
    return CommandRun(Detail(command), Count(code), Detail(tail(output)), Detail(reused))


def suite_commands(profile: Profile) -> SuiteCommands:
    """The test commands the profile declares, beside the test keys its `required:` names, and the policy's keys."""
    required = {part for part in re.split(r"[\s,]+", str(profile.get("required") or "").strip()) if part}
    wanted = sorted(set(test_command_keys(profile)) | {r for r in required if r == "e2eTest" or r.startswith("test.")})
    return SuiteCommands(tuple((CommandKey(k), Detail(str(profile[k])) if profile.get(k) else None) for k in wanted),
                         frozenset(CommandKey(r) for r in required))
