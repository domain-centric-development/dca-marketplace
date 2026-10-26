"""A story's branch against the main line, as git holds it: the target it integrates into, the tests the main line
changed while the story ran and the lines of them a merge's resolution lost."""

from __future__ import annotations

import collections
import difflib
import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home, runs_top
from .repository import git, git_blob
from ..files.decision_record_files import records_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..claims.remote_claims import claim_config_here, remote_main
from ..files.run_marks import write_mark
from ..files.kept_files import meaningful_lines, TESTS_BASELINE
from ..files.delivery_files import SKIP_DIRS, TEST_FILE
from ....domain.model.decision_record import ANSWERED_WORDS


def tree_tests(cwd: str, tree: typing.Optional[str]) -> typing.Optional[typing.Dict[str, str]]:
    """{test file: blob} of a tree object, relative to the project as `test_files` finds them; None without one."""
    if not tree or tree == "none":
        return None
    code, out = git(cwd, "ls-tree", "-r", "-z", tree)
    if code:
        return None
    skipped = SKIP_DIRS | {runs_top()}
    found: typing.Dict[str, str] = {}
    for entry in out.split("\0"):
        meta, _, rel = entry.partition("\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob" or not TEST_FILE.search(os.path.basename(rel)):
            continue
        if any(d in skipped or d.startswith(".") for d in rel.split("/")[:-1]):
            continue
        found[rel] = parts[2]
    return found


def rebase_tests_baseline(cwd: str, runs: str, story_id: str, new: typing.Optional[str],
                          old: typing.Optional[str] = None) -> None:
    """After the runner brought the main line into a story's branch: "existed before this story" is the main line
    as it was merged. Every test in the main line's tree `new` is held to the main line's version, so a test the
    main line changed while the story waited is not the story's change; one the main line removed leaves the
    baseline (where `old`, the base before, says it was tracked). `new` is the main line's tree, never the story's
    branch — nothing the story changed, committed by the runner before the merge or not, gets into the baseline."""
    path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
    main = tree_tests(cwd, new)
    if not os.path.isfile(path) or main is None:
        return
    before = tree_tests(cwd, old) or {}
    entries: typing.Dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "  " in line:
            blob, rel = line.split("  ", 1)
            entries[rel] = blob
    rebased = {rel: blob for rel, blob in entries.items() if rel in main or rel not in before}
    rebased.update(main)
    if rebased != entries:
        write_mark(runs, story_id, TESTS_BASELINE, "\n".join(f"{blob}  {rel}" for rel, blob in sorted(rebased.items())))


#: The main line's side of the tests a merge met (#151): written when merging the main line into a story stops on a
#: conflict — every test file the main line changed since the story's base, as `<base blob | ->\t<main blob>\t<file>`
#: — so the integrate gate tells a resolution that dropped what the main line added to a test from the story's own
#: change, and the runner sends it back to the integrate stage.
MAIN_TESTS = "main-tests"


def record_main_tests(cwd: str, runs: str, story_id: str, target: str) -> None:
    """During a merge that stopped on conflicts in the story's worktree (`HEAD` the story, `target` the main line):
    the test files the main line changed since the two parted, with both versions. Nothing to hold, no record."""
    base = git(cwd, "merge-base", "HEAD", target)[1].strip()
    before, main = tree_tests(cwd, base) or {}, tree_tests(cwd, target) or {}
    rows = [f"{before.get(rel, '-')}\t{blob}\t{rel}" for rel, blob in sorted(main.items()) if before.get(rel) != blob]
    path = os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)
    if rows:
        write_mark(runs, story_id, MAIN_TESTS, "\n".join(rows))
    elif os.path.isfile(path):
        os.remove(path)


def main_tests_lost(cwd: str, runs: str, story_id: str,
                    waive: bool = True) -> typing.List[typing.Tuple[str, typing.List[str]]]:
    """[(test file, [line, …])]: what the main line added to a test while the story ran that the story's tree no
    longer holds — a case another story added, an assertion it changed. Lines the main line kept from the base are
    the story's to change (and `tests-kept` holds the story to them); the main line's own lines are not. A file an
    answered integrate decision names is the person's to settle (`waive`, #163): it is left out."""
    lost = _main_tests_lost(cwd, runs, story_id)
    return [(rel, lines) for rel, lines in lost if not main_tests_waiver(cwd, story_id, rel)] if waive else lost


def main_tests_adapted(cwd: str, runs: str, story_id: str) -> typing.List[typing.Tuple[str, typing.List[str]]]:
    """[(test file, [line, …])]: the main line's test lines the merge rewrote to a name the story re-signed (#163)."""
    adapted: typing.List[typing.Tuple[str, typing.List[str]]] = []
    _main_tests_lost(cwd, runs, story_id, adapted)
    return adapted


def main_tests_waiver(cwd: str, story_id: str, rel: str) -> typing.List[str]:
    """The ids of the story's answered integrate decisions that name this test file — by its path or its file name, as
    a record names it — a person answered how its
    main-line lines are resolved, so the check holds the resolution to that answer, not to the lines (#163). Read in
    the main checkout, where the records are: the integrate step has taken the worktree's links down."""
    try:
        records = records_of(story_id, cwd=factory_home() or cwd)
    except (GateError, OSError):
        return []
    return [str(front.get("id", "")).strip() for _p, front, body, state, _a in records
            if state in ANSWERED_WORDS and str(front.get("stage", "")).strip() == "integrate"
            and (rel in body or re.search(rf"(?<![\w./-]){re.escape(os.path.basename(rel))}(?![\w.-])", body))]


#: A name called or declared on a line: `Name(`, `obj.Name(`, `new Name(` — the words before a parenthesis that are no
#: statement of the language.
CALLED = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^<>()]*>)?\s*\(")


NOT_CALLS = {"if", "for", "foreach", "while", "switch", "catch", "return", "new", "typeof", "nameof", "sizeof", "lock",
             "using", "fixed", "base", "this", "super", "await", "throw", "when", "assert", "synchronized", "with"}


#: A name declared on a line: a word — a type, a modifier, `def`, `record` — then the name and its parameters
#: (`public Money Total(`, `record Command(`, `def total(`); never `.Name(`, `= Name(`, `return Name(`, `new Name(`.
DECLARED = re.compile(r"(?:^|\s)([A-Za-z_][\w.<>\[\],?]*[\w>\]?]|>)\s+([A-Za-z_]\w*)\s*(?:<[^<>()]*>)?\s*\(")


NOT_DECLARING = {"return", "new", "await", "throw", "yield", "else", "case", "in", "is", "as", "and", "or", "not",
                 "await", "typeof", "nameof", "var", "val", "let"}


def called_names(line: str) -> typing.Set[str]:
    return {name for name in CALLED.findall(line) if name not in NOT_CALLS}


def declared_names(line: str) -> typing.Set[str]:
    return {name for before, name in DECLARED.findall(line)
            if before.split(".")[-1] not in NOT_DECLARING and name not in NOT_CALLS}


def rewritten(line: str, lines: typing.Iterable[str]) -> bool:
    """Whether the file still has `line` in another form — a line alike to at least 60 % — so a missing line is not
    a case that went whole."""
    for other in lines:
        matcher = difflib.SequenceMatcher(None, line, other, autojunk=False)
        if matcher.real_quick_ratio() >= 0.6 and matcher.quick_ratio() >= 0.6 and matcher.ratio() >= 0.6:
            return True
    return False


def resigned_names(cwd: str, target: str) -> typing.Set[str]:
    """The names the story's own change in production code re-signed or removed: every name declared on a line of a
    non-test file the story's tree no longer has as `target` (the main line) has it. A main-line test line that calls
    one of them was adapted to the story's new signature, or could not compile — not lost (#163)."""
    code, diff = git(cwd, "diff", "--no-color", "--unified=0", target, "--")
    if code:
        return set()
    names: typing.Set[str] = set()
    test = False
    for line in diff.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            rel = line[4:].strip()
            if rel != "/dev/null":
                test = bool(TEST_FILE.search(os.path.basename(rel[2:] if rel[:2] in ("a/", "b/") else rel)))
            continue
        if line[:1] == "-" and not test:
            names |= declared_names(line[1:])
    return names


def _main_tests_lost(cwd: str, runs: str, story_id: str,
                     adapted: typing.Optional[typing.List[typing.Tuple[str, typing.List[str]]]] = None
                     ) -> typing.List[typing.Tuple[str, typing.List[str]]]:
    """The main line's added test lines the story's tree lacks. A missing line that calls a name the story's own
    production change re-signed or removed is the merge adapting another story's helper to it — collected in
    `adapted`, not lost; a test case's own lines (its head, its attributes) name no such name and stay asked for."""
    path = os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)
    if not os.path.isfile(path):
        return []
    lost: typing.List[typing.Tuple[str, typing.List[str]]] = []
    resigned: typing.Optional[typing.Set[str]] = None
    for line in read_text(path).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        before_blob, main_blob, rel = parts
        code, main_text = git_blob(cwd, main_blob)
        if code:
            continue
        base_text = "" if before_blob == "-" else git_blob(cwd, before_blob)[1]
        # compared without their indentation: a resolution may indent a case anew
        was = [l.strip() for l in meaningful_lines(base_text, rel)]
        main = [l.strip() for l in meaningful_lines(main_text, rel)]
        added = [main[j] for tag, _i1, _i2, j1, j2 in
                 difflib.SequenceMatcher(None, was, main, autojunk=False).get_opcodes()
                 if tag in ("insert", "replace") for j in range(j1, j2)]
        full = os.path.join(cwd, rel)
        if not os.path.isfile(full):
            lost.append((rel, ["(the file is gone)"]))
            continue
        with open(full, encoding="utf-8", errors="replace") as handle:
            now = [l.strip() for l in meaningful_lines(handle.read(), rel)]
        left = collections.Counter(now)
        missing = []
        for wanted in added:
            if left[wanted] > 0:
                left[wanted] -= 1
            else:
                missing.append(wanted)
        if missing:
            if resigned is None:
                target = merge_target(runs, story_id, cwd)
                resigned = resigned_names(cwd, target) if target else set()
            kept = [line for line in missing if called_names(line) & resigned and rewritten(line, now)]
            if kept and adapted is not None:
                adapted.append((rel, kept))
            missing = [line for line in missing if line not in kept]
        if missing:
            lost.append((rel, missing))
    return lost


def lost_text(lost: typing.Iterable[typing.Tuple[str, typing.Sequence[str]]]) -> str:
    """The lost lines as a reader takes them in: each file with its first lines."""
    return "; ".join(f"{rel} lost {', '.join(repr(l) for l in lines[:2])}"
                     + (f" and {len(lines) - 2} more line(s)" if len(lines) > 2 else "") for rel, lines in lost)


CONFLICT_MARKER = re.compile(r"^(<{7} |={7}$|>{7} )", re.M)


def integration_target(runs: str, story_id: str) -> str:
    """The branch of the main checkout the story integrates into — recorded when its worktree was made."""
    path = os.path.join(evidence_dir(runs, story_id), "target")
    return read_text(path).strip() if os.path.isfile(path) else ""


def merge_target(runs: str, story_id: str, cwd: typing.Optional[str] = None) -> str:
    """What a story integrates against: the main checkout's branch — or, where the profile claims stories on a remote
    (WP-93), that branch as the remote has it, fetched: the main line every factory shares."""
    target = integration_target(runs, story_id)
    config = claim_config_here(factory_home() or cwd)
    return remote_main(config["remote"], target) if config and target else target
