"""The tests a story holds to, as files: the red ledger and the version of each test seen failing, the tests that
existed before the story and how they changed since, the plan's changed tests."""

from __future__ import annotations

import calendar
import contextlib
import os
import re
import time
import typing
from .story_layout import file_digest
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from ..git.repository import git
from .decision_record_files import NOTHING
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .design_files import ASSERTION_STATEMENT
import shutil
import subprocess
import tempfile
from .owned_files import run_owned
from .delivery_files import TEST_DIR, TEST_FILE
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..pipeline.stage_rows import STAGES
from .decision_record_files import answered_decisions
from .run_marks import last_ended
from .test_files import read_mapping
from .test_files import locate_tests
from ....domain.model.stage_story import Presence
from ....domain.model.story_state import Detail
from ....domain.service.kept_checks import KeptChecks


#: A cited path usually carries where in the file it was read: `README.md:149`, `Book.cs:28-31`,
#: `guide.md#anchor`. The location is not part of the file name, so it is stripped before the file
#: is looked up — otherwise naming the line makes an existing file look missing.
LOCATION_SUFFIX = re.compile(r"(?::L?\d+(?:[-–:]\d+)?|#[\w.-]+)$")


def bare_path(name: str) -> str:
    return LOCATION_SUFFIX.sub("", name.strip().strip("`")).strip()


def row_cells(line: str) -> typing.List[str]:
    """Cells of a markdown table row, or an empty list when the line is not one."""
    if not line.startswith("|"):
        return []
    return [cell.strip() for cell in line.strip("|").split("|")]


def unproven_tests(cwd: str, located: typing.Dict[str, str], digests: typing.Dict[str, typing.Optional[str]]
                   ) -> typing.List[str]:
    """`<selector> (<file>)` for each test whose file is no longer the version its red proof was taken against."""
    moved: typing.List[str] = []
    for selector, digest in sorted(digests.items()):
        test_file = located.get(selector)
        if not digest or not test_file or not os.path.isfile(os.path.join(cwd, test_file)):
            continue
        if file_digest(os.path.join(cwd, test_file)) != digest:
            moved.append(f"{selector} ({test_file})")
    return moved


#: The tree at the test gate's pass (WP-151 A): the production code as the test stage left it — stubs that refuse to
#: answer — and the tests seen red. The tidy gate rebuilds it with tidy's tests laid over, to see them red again.
RED_TREE = "red-tree"


def red_tree(runs: str, story_id: str) -> typing.Optional[str]:
    """The recorded red tree's id, or None (an older story, outside git)."""
    path = os.path.join(evidence_dir(runs, story_id), RED_TREE) if runs and story_id else None
    tree = read_text(path).strip() if path and os.path.isfile(path) else ""
    return tree if tree and tree != "none" else None


def tidy_moves(cwd: str, runs: str, story_id: str, located: typing.Dict[str, str]) -> typing.List[str]:
    """The mapped tests whose file changed since the test stage saw them fail, by selector."""
    return [selector for selector, digest in sorted(read_red_digests(runs, story_id).items())
            if digest and located.get(selector) and os.path.isfile(os.path.join(cwd, located[selector]))
            and file_digest(os.path.join(cwd, located[selector])) != digest]


#: Which selectors the test stage saw fail. Kept as a file next to the round counter for the same
#: reason: the build gate must not take a stage's word that a test was red once.
def red_ledger_path(runs: str, story: str) -> typing.Optional[str]:
    if not runs or not story:
        return None
    return os.path.join(evidence_dir(runs, story), ".tests-red")


def read_red_digests(runs: str, story: str) -> typing.Dict[str, typing.Optional[str]]:
    """{selector: sha256 of its test file when it was recorded red, or None for an older ledger}.

    A red proof is a proof about one version of a test. The digest binds it to that version, so a
    test weakened after it was seen failing no longer carries the proof into the build gate."""
    path = red_ledger_path(runs, story)
    if not path or not os.path.isfile(path):
        return {}
    digests: typing.Dict[str, typing.Optional[str]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            selector, _, digest = line.strip().partition("\t")
            if selector:
                digests[selector] = digest.strip() or None
    return digests


def human_line(text: str) -> bool:
    """A line a person wrote: not empty, not "none", not a template placeholder or an HTML comment."""
    text = re.sub(r"<!--.*?-->", "", text).strip()
    return bool(text) and text.lower() not in NOTHING and "{{" not in text


def changed_tests_in_plan(runs: str, story_id: str) -> typing.Dict[str, str]:
    """{test file: backed-by cell} from the plan's `## Changed tests` table."""
    path = os.path.join(runs, story_id, "plan.md")
    rows: typing.Dict[str, str] = {}
    if not os.path.isfile(path):
        return rows
    for line in section_of(read_text(path), "changed tests") or []:
        cells = row_cells(line.strip())
        if len(cells) < 2 or cells[0].lower() in ("test file", "file") or set(cells[0]) <= {"-", " "}:
            continue
        name = cells[0].strip("`").strip()
        if name.lower() not in NOTHING:
            rows[bare_path(name).replace(os.sep, "/")] = cells[-1]
    return rows


# What a test file's lines mean once comments are gone: an added `/* … */` around an old assertion keeps
# every old line in the text and takes it out of the test. Applied to both versions alike, so a line
# the story left alone compares equal whatever the stripping does to it.
HASH_COMMENTS = (".py", ".rb", ".ex", ".exs")


BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


TRIPLE_QUOTED = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.S)


DISABLED_BLOCK = re.compile(r"^[ \t]*#if\s+(false|0)\b.*?^[ \t]*#endif\b", re.S | re.M)


# Lines that switch a test off without touching what it asserts: an added one is a changed test.
SKIP_MARKER = re.compile(
    r"@Disabled\b|@Ignore\b|@DisabledIf|@EnabledIf|\[Ignore\b|\bSkip\s*=|@pytest\.mark\.(skip|xfail)"
    r"|\bpytest\.skip\(|\bunittest\.skip|@skip\b|\b(xit|xdescribe|xtest|fit|fdescribe)\s*\("
    r"|\.(skip|only|todo)\s*\(|\bt\.Skip(Now|f)?\(|\bskip\s+[\"']")


def meaningful_lines(text: str, path: str) -> typing.List[str]:
    if path.endswith(HASH_COMMENTS):
        text = TRIPLE_QUOTED.sub("", text)
        lines = [re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines()]
    else:
        text = DISABLED_BLOCK.sub("", BLOCK_COMMENT.sub("", text))
        lines = [re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines()]
    return [line.rstrip() for line in lines if line.strip()]


TOKEN = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\w+")


def statements(text: str) -> typing.List[typing.List[str]]:
    """The statements of a test source, each as its word and literal tokens: split at `;`, at a brace, and at a line
    end outside brackets unless the next line goes on with `.` (a call chain) — the shapes Java, C#, Kotlin, JS and
    Python test files are written in."""
    out: typing.List[str] = []
    current: typing.List[str] = []
    depth, quote, escaped = 0, "", False
    lines = text.splitlines()
    for index, line in enumerate(lines):
        for char in line:
            if quote:
                current.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in "\"'":
                quote = char
            elif char in "([":
                depth += 1
            elif char in ")]":
                depth = max(depth - 1, 0)
            if char in ";{}" and depth == 0:
                out.append("".join(current))
                current = []
                continue
            current.append(char)
        following = next((l.strip() for l in lines[index + 1:] if l.strip()), "")
        if depth == 0 and not following.startswith(".") and not line.rstrip().endswith((".", ",", "+", "&&", "||")):
            out.append("".join(current))
            current = []
        else:
            current.append("\n")
    out.append("".join(current))
    return [TOKEN.findall(statement) for statement in out if statement.strip()]


def assertions_kept(before: str, now: str) -> bool:
    """Whether every assertion the old test made is still made: each old assertion statement's tokens appear, in
    order, in a statement of the new version that is an assertion too — more arguments, never fewer, never another
    expected value. A changed arrangement (a constructor that gained a field, a renamed local) passes; a changed
    expectation, a removed assertion or a weaker matcher does not."""
    old = [tokens for tokens in statements(before) if ASSERTION_STATEMENT.search(" ".join(tokens))]
    new = [tokens for tokens in statements(now) if ASSERTION_STATEMENT.search(" ".join(tokens))]
    if not old:
        return False
    def within(small: typing.List[str], large: typing.List[str]) -> bool:
        rest = iter(large)
        return all(any(token == other for other in rest) for token in small)
    used: typing.Set[int] = set()
    for tokens in old:
        match = next((i for i, candidate in enumerate(new) if i not in used and within(tokens, candidate)), None)
        if match is None:
            return False
        used.add(match)
    return True


def switched_off(before: typing.List[str], now: typing.List[str]) -> bool:
    """Whether the new version carries more skip markers than the old one."""
    def count(lines: typing.List[str]) -> int:
        return sum(1 for line in lines if SKIP_MARKER.search(line))
    return count(now) > count(before)


def stage_windows(runs: str, story_id: str) -> typing.List[typing.Tuple[int, float]]:
    """(start, end) of every stage window in the story's journal, as epoch seconds; an open one ends now."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    windows: typing.List[typing.Tuple[int, float]] = []
    open_: typing.Dict[str, int] = {}
    if not os.path.isfile(journal):
        return windows
    def stamp(text: str) -> int:
        return calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S"))
    for line in read_text(journal).splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or parts[1] not in ("stage-start", "stage-end"):
            continue
        with contextlib.suppress(ValueError):
            if parts[1] == "stage-start":
                open_[parts[2]] = stamp(parts[0])
            elif parts[2] in open_:
                windows.append((open_.pop(parts[2]), stamp(parts[0])))
    windows += [(start, time.time()) for start in open_.values()]
    return windows


def committed_by_a_stage(cwd: str, runs: str, story_id: str, rel: str) -> bool:
    """Whether a commit that changed `rel` was made inside one of the story's stage windows. A stage commits
    nothing; a commit in its window is the stage's change, and the story is held to it like any other."""
    windows = stage_windows(runs, story_id)
    if not windows:
        return False
    code, out = git(cwd, "log", "--format=%ct", "-n", "50", "--", rel)
    if code:
        return False
    return any(start - 1 <= int(t) <= end + 1 for t in out.split() if t.isdigit() for start, end in windows)


# A story may add tests and add cases to a test file; it may not change what a test that existed
# before it expects, unless a human decided that. The plan gate runs before any stage of the story
# touches a test, so it records the test files as git blobs; later gates compare against them.
TESTS_BASELINE = ".tests-baseline"


def is_test_path(path: str) -> bool:
    """A test file by its name, or any file below a test folder — the support a test uses beside the tests."""
    parts = path.replace("\\", "/").split("/")
    return bool(TEST_FILE.search(parts[-1])) or any(TEST_DIR.search(part) for part in parts[:-1])


@contextlib.contextmanager
def red_tree_copy(cwd: str, runs: str, tree: str) -> typing.Iterator[str]:
    """A scratch copy of the red tree with every test file and test-support file of the working tree laid over it —
    a test path the tree has and the working tree lost is removed. Removed afterwards; the tree is never touched."""
    scratch = tempfile.mkdtemp(prefix="dca-reproof-")
    try:
        copy = os.path.join(scratch, "tree")
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(scratch, "index"))
        for args in (["read-tree", tree], ["checkout-index", "-a", "-f", f"--prefix={copy}/"]):
            done = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True, text=True)
            if done.returncode != 0:
                raise GateError(f"the red tree {tree[:12]} cannot be read back: {(done.stderr or '').strip()[:200]}")
        listed = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", tree], cwd=cwd, capture_output=True)
        now = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=cwd,
                             capture_output=True)
        names = {n for out in (listed.stdout, now.stdout) for n in out.decode("utf-8", "replace").split("\0") if n}
        for name in sorted(n for n in names if is_test_path(n) and not run_owned(n, runs)):
            source, target = os.path.join(cwd, name), os.path.join(copy, name)
            if os.path.isfile(source):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
            elif os.path.lexists(target) and not os.path.lexists(source):
                os.remove(target)
        yield copy
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def write_red_ledger(runs: typing.Optional[str], story: typing.Optional[str], selectors: typing.Collection[str],
                     located: typing.Optional[typing.Mapping[str, typing.Optional[str]]] = None, cwd: str = ".",
                     kept: typing.Optional[typing.Mapping[str, typing.Optional[str]]] = None) -> None:
    """The red record: every selector seen red now, bound to its test file's digest — and, in `kept`, the
    entries an earlier run made that this run could neither confirm nor replace (a strengthened test whose
    break is still missing keeps its old proof, so the next run can prove the new version instead of
    treating a test it once saw red as one it never did)."""
    path = red_ledger_path(runs or "", story or "")
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    for selector in sorted(set(selectors) | set(kept or {})):
        if selector not in selectors:
            digest = (kept or {}).get(selector)
            lines.append(f"{selector}\t{digest}" if digest else selector)
            continue
        test_file = (located or {}).get(selector)
        full = os.path.join(cwd, test_file) if test_file else None
        lines.append(f"{selector}\t{file_digest(full)}" if full and os.path.isfile(full) else selector)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + ("\n" if lines else ""))


def stale_red_proof(cwd: str, runs: str, story: str, start: typing.Optional[str] = None) -> typing.List[str]:
    """The tests whose red proof the build and tidy gates would refuse (`red-proof`), read without running anything:
    each mapped test whose file changed after the test stage saw it fail — by a merge of the main line into the story,
    most often — and no answered decision of stage `test` changed what it expects. Empty without a red record."""
    digests = read_red_digests(runs, story)
    if not digests or all(d is None for d in digests.values()):
        return []
    try:
        _path, mapping = read_mapping(runs, story)
    except GateError:
        return []
    moved = unproven_tests(cwd, locate_tests(cwd, mapping)[0] if mapping else {}, digests)
    decided = Presence.PRESENT if moved and answered_decisions(cwd, story, "test") else Presence.ABSENT
    # A tidy that runs again moved the tests itself: its gate re-proves them on the red tree (WP-151 A).
    reproof = Presence.PRESENT if start == "tidy" and red_tree(runs, story) and last_ended(
        runs, story, tuple(s.name for s in STAGES if s.lists and not s.red)) == "tidy" else Presence.ABSENT
    return [m.value for m in KeptChecks.stale(tuple(Detail(m) for m in moved), decided, reproof)]
