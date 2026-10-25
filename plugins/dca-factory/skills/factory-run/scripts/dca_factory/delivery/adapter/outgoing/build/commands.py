"""The profile's commands as the gate runs them: through a POSIX shell, recorded by the runner on an unchanged
tree, the test command that covers a test file, the filter that selects tests, and what a run's output says."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import typing
from datetime import datetime, timezone
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, runs_top
from ..git.repository import git
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .test_reports import clock_marker, executed_tests, fill, normalise, report_state, reports_from_this_run, SENTINEL
from ..files.owned_files import run_owned
from ..files.delivery_files import SKIP_DIRS

#: The tools' own folders in a project: never part of what a recorded run is keyed by.
TOOL_FOLDERS = ("/.claude/", "/.codex/", "/.opencode/")


def posix_shell() -> typing.Optional[str]:
    """On Windows, the bash that runs profile commands; None elsewhere (the system shell does).

    Not `shutil.which("bash")`: on a stock Windows that is `System32\\bash.exe`, the WSL launcher,
    which starts a Linux distribution or fails without one — either way not a shell over this
    tree. Order: `FACTORY_BASH`; the bash of the Git installation that `git` on PATH belongs to
    (Git Bash, the supported route); any other `bash.exe` on PATH outside System32.
    """
    if os.name != "nt":
        return None
    named = os.environ.get("FACTORY_BASH", "").strip()
    if named:
        return named
    git = shutil.which("git")
    if git:
        install = os.path.dirname(os.path.dirname(os.path.realpath(git)))     # <Git>/cmd/git.exe
        for relative in ("bin/bash.exe", "usr/bin/bash.exe", "../bin/bash.exe"):
            candidate = os.path.normpath(os.path.join(install, relative))
            if os.path.isfile(candidate):
                return candidate
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(entry, "bash.exe")
        if os.path.isfile(candidate) and "system32" not in candidate.lower():
            return candidate
    return None


# Commands whose shell could not find their program, in the order they were met. A missing tool is the
# environment's fault, not the story's: the report names it as `environment`, and the runner stops once
# on it instead of sending a stage into rounds it cannot win.
MISSING_TOOLS: typing.List[typing.Tuple[str, str]] = []


MISSING_TOOL = re.compile(r"(?:^|\n)(?:[^\n:]*: )?(?:line \d+: |\d+: )?([^\s:]+): (?:command )?not found"
                          r"|'([^']+)' is not recognized as an internal or external command")


def missing_tool(code: int, output: typing.Optional[str]) -> typing.Optional[str]:
    """The program a shell could not find (exit 127, or cmd.exe's 9009), else None."""
    if code not in (127, 9009):
        return None
    found = MISSING_TOOL.search(output or "")
    return (found.group(1) or found.group(2)) if found else "a program"


def run(command: str, cwd: str) -> typing.Tuple[int, str]:
    """Run one profile command through a shell.

    The profile is written for a POSIX shell — `a && b`, `sh runner.sh`, quoting — and the runner
    and the commit hook are bash, so on Windows the same commands go through Git's bash (see
    `posix_shell`). Without one, `cmd.exe` gets them, and a profile that leans on POSIX syntax
    fails there loudly rather than subtly.
    """
    bash = posix_shell()
    if bash:
        completed = subprocess.run(
            [bash, "-c", command], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    else:
        completed = subprocess.run(
            command, cwd=cwd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    output = completed.stdout + completed.stderr
    tool = missing_tool(completed.returncode, output)
    if tool and (tool, command) not in MISSING_TOOLS:
        MISSING_TOOLS.append((tool, command))
    return completed.returncode, output


#: The runner's own record of the suite runs its gates made on one tree (WP-79 A3). Set by `main()` when
#: `--record-suites` is on and the runner's key is in the environment; None in a stage's own gate run.
SUITES_RECORD: typing.Optional[typing.Dict[str, typing.Any]] = None


def suites_tree_key(cwd: str, runs: str) -> str:
    """What a recorded run is keyed by: a digest of every source file's path and content — the run folder,
    the tools' folders and the build outputs left out — plus HEAD where there is one. The gate report the
    runner copies into the evidence folder between two gates must not turn an unchanged tree into a new one, and a
    project before its `git init` has a tree as well."""
    digest = hashlib.sha256()
    code, head = git(cwd, "rev-parse", "HEAD")
    digest.update((head.strip() if code == 0 else "no-head").encode("utf-8"))
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith("."))
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, cwd).replace(os.sep, "/")
            if run_owned(rel, runs) or any(folder in "/" + rel for folder in TOOL_FOLDERS):
                continue
            try:
                with open(path, "rb") as handle:
                    digest.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(handle.read()).digest())
            except OSError:
                continue
    return digest.hexdigest()


def suites_signature(key: str, tree: str, invocation: str, code: typing.Any, ran_json: str) -> str:
    return hmac.new(key.encode("utf-8"), f"{tree}\t{invocation}\t{code}\t{ran_json}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def open_suites_record(cwd: str, runs: str, story_id: str, key: str) -> typing.Dict[str, typing.Any]:
    """The rows of `.verify/suites.tsv` for this tree whose signature the runner's key confirms. A row
    written by anything else — a stage, a hand — carries no valid signature and is not read."""
    path = os.path.join(evidence_dir(runs, story_id), "suites.tsv")
    tree = suites_tree_key(cwd, runs)
    rows: typing.Dict[str, typing.Tuple[str, int, typing.Any]] = {}
    if tree and os.path.isfile(path):
        for line in read_text(path).splitlines():
            parts = line.split("\t")
            if len(parts) != 6:
                continue
            when, row_tree, invocation, code, ran_json, signature = parts
            if row_tree == tree and hmac.compare_digest(
                    signature, suites_signature(key, row_tree, invocation, code, ran_json)):
                rows[invocation] = (when, int(code), json.loads(ran_json))
    return {"path": path, "key": key, "tree": tree, "rows": rows, "cwd": os.path.realpath(cwd)}


def recorded_run(
    invocation: str,
    cwd: str,
    profile: typing.Any = None,
    with_reports: bool = False,
) -> typing.Tuple[int, str, typing.Dict[typing.Tuple[str, str], str], str]:
    """(code, output, ran, reused) — the invocation run now, or the runner's own record of it on this tree.

    Only a run that passed is recorded: a red run is run again, so a fix is seen by the run that judges
    it. `ran` is what the reports of the run said was executed (empty when `with_reports` is off), and
    `reused` is the suffix that tells the reader the verdict came from the record."""
    record = SUITES_RECORD
    if record and record.get("cwd") != os.path.realpath(cwd):
        record = None                         # another tree — a break's scratch copy — has no record of its own
    if record and record["tree"] and invocation in record["rows"]:
        when, code, ran_rows = record["rows"][invocation]
        return code, "", {(cls, method): outcome for cls, method, outcome in ran_rows}, \
            f" (recorded at {when} for this tree)"
    if with_reports:
        before, marker = report_state(cwd, profile), clock_marker(cwd)
        code, output = run(invocation, cwd)
        ran = executed_tests(reports_from_this_run(before, report_state(cwd, profile), marker))
    else:
        code, output = run(invocation, cwd)
        ran = {}
    if record and record["tree"] and code == 0 and not any(outcome == "failed" for outcome in ran.values()):
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ran_json = json.dumps(sorted([cls, method, outcome] for (cls, method), outcome in ran.items()))
        signature = suites_signature(record["key"], record["tree"], invocation, code, ran_json)
        os.makedirs(os.path.dirname(record["path"]), exist_ok=True)
        with open(record["path"], "a", encoding="utf-8") as handle:
            handle.write("\t".join((when, record["tree"], invocation, str(code), ran_json, signature)) + "\n")
        record["rows"][invocation] = (when, code, json.loads(ran_json))
    return code, output, ran, ""


#: Which declared command can run a given test. A mapped test may live in any test project or
#: source set — the end-user tests in one, the unit tests in another — and running a selector
#: against the wrong one matches nothing. A runner that matched nothing exits 0, which is
#: indistinguishable from a passing test, so the choice may not be a guess: it is made from the
#: file the test was found in.
TEST_COMMAND_KEYS = ("e2eTest", "test")


def test_command_keys(profile: typing.Mapping[str, typing.Any]) -> typing.List[str]:
    """Every command in the profile that runs tests, most specific first.

    A project has more than two test source sets — unit, integration, end-user — and a mapped
    test may live in any of them. Beyond the two fixed keys, any `test.<name>:` entry counts, so
    declaring one more source set is a profile line and never a change to the gate.
    """
    extra = sorted(key for key in profile if key.startswith("test."))
    return extra + list(TEST_COMMAND_KEYS)


def command_for(
    profile: typing.Mapping[str, typing.Any], test_path: str
) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    """The (key, command) whose path or source-set token covers `test_path`, longest match first.

    A command names where it runs: `dotnet test tests/Foo.HttpTests`, `./gradlew test-e2e`
    (source set `src/test-e2e/java`). Both forms are matched against the file's path segments.
    """
    segments = [part for part in test_path.replace("\\", "/").split("/") if part]
    joined = "/".join(segments)
    best = None
    for key in test_command_keys(profile):
        command = profile.get(key)
        if not command:
            continue
        for token in command.split():
            token = token.strip("\"'").lstrip("./")
            if not token or token.startswith("-"):
                continue
            # A project or solution file names a directory, not a file to match: `dotnet test
            # tests/Foo/Foo.csproj` runs every test under tests/Foo.
            if os.path.splitext(token)[1] in (".csproj", ".fsproj", ".vbproj", ".sln", ".slnx",
                                              ".slnf", "pom.xml"):
                token = os.path.dirname(token) or token
            if "/" not in token and "." in token and not token.startswith("test"):
                continue                      # a version, a flag's value, a class name
            covers = token in segments or ("/" in token and token in joined)
            if covers and (best is None or len(token) > best[2]):
                best = (key, command, len(token))
    if best:
        return best[0], best[1]
    # No guessing beyond this point. Whether a command without a path runs the whole project
    # (`dotnet test` on a solution) or exactly one source set (`./gradlew test`) is knowledge about
    # that build tool, and a gate that guesses it either refuses valid projects or silently runs the
    # wrong task and calls a criterion covered that nothing executes. So the project declares it:
    #
    #     covers.test: **                  this command runs every test in the project
    #     covers.test: tests/, src/it/     it runs the tests under these paths
    #
    # The installer writes it where it can tell; a human corrects it where it cannot.
    for key in test_command_keys(profile):
        scope = profile.get(f"covers.{key}")
        if not scope or not profile.get(key):
            continue
        for prefix in (part.strip() for part in scope.split(",")):
            if prefix == "**" or (prefix and joined.startswith(prefix.rstrip("/").lstrip("./"))):
                return key, profile[key]
    return None, None


def discriminates(
    command: str, flag: str, fmt: str, cwd: str, cache: typing.Dict[str, typing.Tuple[int, str]]
) -> typing.Tuple[int, str]:
    """(control_code, control_output) for this command, run once and remembered.

    Only used where a project has opted out of report evidence: comparing a real run against a run
    with a selector that cannot exist is weaker — a runner that prints the selector back in its
    "no tests found" line answers differently without having run anything.
    """
    if command not in cache:
        pattern = fill(fmt, SENTINEL[0], SENTINEL[1], SENTINEL[2])
        code, output = run(f'{command} {flag} "{pattern}"'.strip(), cwd)
        cache[command] = (code, normalise(output, cwd))
    return cache[command]


def joined_filter(profile: typing.Mapping[str, typing.Any], flag: str, patterns: typing.Sequence[str]) -> str:
    """The filter argument that selects every pattern in one run.

    The flag repeated per pattern is what most runners take (`--tests a --tests b`, pytest's node ids
    without a flag). A runner that takes one expression joins the patterns inside it instead, with the
    separator the profile names (`filterJoin: "|"` for `dotnet test --filter`, `","` for Maven's
    `-Dtest`). One pattern is the single-selector invocation either way.
    """
    separator = str(profile.get("filterJoin", "") or "")
    if separator and len(patterns) > 1:
        return f'{flag} "{separator.join(patterns)}"'.strip()
    return " ".join(f'{flag} "{pattern}"'.strip() for pattern in patterns)


#: What a browser runner prints when an action, not an expectation, ran out of time.
TIMEOUT_RED = re.compile(r"TimeoutError|Timeout \d+ms exceeded|TimeoutException")


ASSERTION_RED = re.compile(r"expect\(|AssertionError|AssertionFailedError|Expected\b|assert", re.IGNORECASE)


def red_on_timeout(output: typing.Optional[str]) -> bool:
    """A red that came from an action's timeout with no expectation in sight."""
    return bool(TIMEOUT_RED.search(output or "")) and not ASSERTION_RED.search(output or "")


def tail(output: str, limit: int = 1200) -> str:
    text = output.strip()
    return text[-limit:] if len(text) > limit else text
