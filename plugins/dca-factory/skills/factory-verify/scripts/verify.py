#!/usr/bin/env python3
"""Verify the factory itself — the gate's checks and the runner's shape.

The gate is the correctness argument for every stage, so it needs an argument of its own that is
not "an agent said it worked". This builds a throwaway project per case, calls the real
`story-gate.py` command line, and asserts on the check names it reports.

    verify.py [--gate <path>] [--runner <path>] [-v]

Exit code 0 means every case behaved as specified. Dependency-free: standard library only, and the
fixture's "test runner" is a marker file, so red and green cost milliseconds instead of a build.
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

# The reports use `—` and `→`. A Windows console decodes stdout as cp1252 and a Python that
# inherits that raises on the first arrow; the files this writes are UTF-8 in every other respect,
# so the streams are too.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))


def can_symlink():
    """Whether `ln -s` in the runner's shell makes a symlink — asked the way the installer asks it,
    not through `os.symlink`: on Windows an administrator's Python can link while MSYS's `ln -s`
    still copies, and the two answers would send the install and these cases different ways.
    Where the shell cannot link, `install` copies, and the link cases here have no subject."""
    with tempfile.TemporaryDirectory() as probe:
        with open(os.path.join(probe, "a"), "w", encoding="utf-8") as handle:
            handle.write("")
        subprocess.run([BASH, "-c", f'ln -s "{shell_path(probe)}/a" "{shell_path(probe)}/b"'],
                       capture_output=True)
        return os.path.islink(os.path.join(probe, "b"))


def tmpdir():
    """A throwaway project directory. `ignore_cleanup_errors`: a fixture that ran `git init` leaves
    read-only objects behind, and on Windows removing those raises — which is nothing about the
    case that ran in it."""
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def shell_path(path):
    """A path as bash reads it on every platform — forward slashes, `C:/…` on Windows."""
    return path.replace("\\", "/")


def posix_shell():
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


#: The bash the runner cases call. The same resolution the gate uses, because the same wrong
#: answer — the WSL launcher — would make every runner case fail with an empty transcript.
BASH = posix_shell() or "bash"
SYMLINKS = can_symlink()
if os.name == "nt":
    print(f"verify: bash → {BASH}; symlinks {'available' if SYMLINKS else 'unavailable, install copies'}")
DEFAULT_GATE = os.path.normpath(os.path.join(HERE, "..", "..", "factory-run", "scripts", "story-gate.py"))
DEFAULT_RUNNER = os.path.normpath(os.path.join(HERE, "..", "..", "factory-run", "scripts", "factory.sh"))

EPIC = """---
id: sample
title: A sample epic
intent: Someone cannot see something they need
goal: They can see it
metric: SomethingHappened
domain_contact: the-expert
---

# A sample epic
"""

STORY = """---
id: STORY-1
epic: sample
status: approved
context: Widgets
title: A sample story
depends_on: []
---

# A sample story

## Acceptance criteria

- shows-the-thing: The reader sees the thing.
- shows-nothing-when-empty: With nothing recorded, the reader sees an empty list, not an error.

## Assumptions

- open: Does an archived thing count?
"""

#: The same two criteria in the scenario form: keyed Given/When/Then scenarios under Gherkin rules.
STORY_SCENARIOS = STORY.replace("""- shows-the-thing: The reader sees the thing.
- shows-nothing-when-empty: With nothing recorded, the reader sees an empty list, not an error.
""", """### Rule: What is recorded is shown

#### shows-the-thing
- Given one thing is recorded
- When the reader opens the list
- Then the list shows the thing

### Rule: An empty record is not an error

#### shows-nothing-when-empty
- Given nothing is recorded
- When the reader opens the list
- Then the list is empty
- And no error is shown

## Out of scope

- Sharing things with others.
""")

TESTS = """# Tests — STORY-1

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-the-thing | com.example.WidgetPageTest#showsTheThing |
| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |
"""

# The fixture's runner: exit 1 while the marker for that test is absent, 0 once it is there. It
# also refuses a selector it cannot see, so "a run that matched nothing" is reproducible too.
#: A runner invoked the way a build tool is — `gradlew <task>`, no path anywhere in the command.
#: The task names the source set: `test` runs src/test, `test-integration` runs src/test-integration.
TASK_RUNNER_STUB = """#!/bin/sh
task=$1; shift
[ "$1" = "--select" ] && shift
selector=$1
simple=$(echo "$selector" | sed 's/.*\\.//; s/#.*//')
case "$task" in
  test) set=src/test ;;
  *)    set="src/$task" ;;
esac
if [ -z "$(find "$set" -name "$simple.java" 2>/dev/null | head -1)" ]; then
  echo "no tests found for given includes: $selector"
  exit 1
fi
cls=$(echo "$selector" | sed 's/#.*//')
method=$(echo "$selector" | sed 's/.*#//')
mkdir -p "build/test-results/$task"
report="build/test-results/$task/TEST-$simple.xml"
if [ -f "green/$(echo "$selector" | tr -d './#')" ]; then
  printf '<testsuite name="%s"><testcase classname="%s" name="%s"/></testsuite>\\n' \\
    "$cls" "$cls" "$method" > "$report"
  echo "BUILD SUCCESSFUL: $selector"
  exit 0
fi
printf '<testsuite name="%s"><testcase classname="%s" name="%s"><failure>no</failure></testcase></testsuite>\\n' \\
  "$cls" "$cls" "$method" > "$report"
echo "FAILED: $selector"
exit 1
"""

RUNNER_STUB = """#!/bin/sh
# The fixture's test runner: it stands in for a build tool, and it behaves like one in the two
# ways that matter here — it only knows the tests in the source set it was pointed at, and a test
# is red until its marker file says otherwise.
#   usage: runner.sh <source-set path> --select <Class>#<method>
set=$1; shift
[ "$1" = "--select" ] && shift
selector=$1
simple=$(echo "$selector" | sed 's/.*\\.//; s/#.*//')
simple_method=$(echo "$selector" | sed 's/.*#//')
if [ -z "$(find "$set" -name "$simple.java" 2>/dev/null | head -1)" ]; then
  echo "no test matched $selector under $set"
  exit "${NO_MATCH_EXIT:-0}"          # a runner that matched nothing: 0 here, non-zero elsewhere
fi
cls=$(echo "$selector" | sed 's/#.*//')
mkdir -p build/test-results/run
report="build/test-results/run/TEST-$simple.xml"
if [ -f "green/$(echo "$selector" | tr -d './#')" ]; then
  printf '<testsuite name="%s"><testcase classname="%s" name="%s"/></testsuite>\\n' \\
    "$cls" "$cls" "$simple_method" > "$report"
  echo "1 test ran, 0 failed: $selector"
  exit 0
fi
printf '<testsuite name="%s"><testcase classname="%s" name="%s"><failure>no</failure></testcase></testsuite>\\n' \\
  "$cls" "$cls" "$simple_method" > "$report"
echo "1 test ran, 1 failed: $selector"
exit 1
"""

PROFILE = """compile: true
test: sh runner.sh src/test/java
test.pages: sh runner.sh src/test-pages/java
filterFlag: --select
filterFormat: "{class}#{method}"
architecture: true
"""

#: The second shape the selector resolves through, with a real runner rather than a stub: tests
#: are functions in a module, the module is named by its path, and pytest writes the JUnit XML the
#: gate reads. The markers under green/ are the same convention the stub runners use.
PYTEST_MODULE = """import os

import pytest


def test_shows_the_thing():
    assert os.path.exists("green/teststest_widgetstest_shows_the_thing")


class TestWidgets:
    def test_shows_nothing_when_empty(self):
        assert os.path.exists("green/teststest_widgetsTestWidgetstest_shows_nothing_when_empty")


@pytest.mark.parametrize("case", ["a", "b"])
def test_in_every_case(case):
    assert os.path.exists(f"green/teststest_widgetstest_in_every_case-{case}")
"""

PYTEST_PROFILE = """test: {python} -m pytest -q --junitxml=test-results/pytest.xml
covers.test: **
filterFormat: "{{file}}::{{method}}"
architecture: true
"""


def pytest_available():
    probe = subprocess.run([sys.executable, "-m", "pytest", "--version"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    return probe.returncode == 0


def pytest_project(criterion, selector, **more):
    """A fixture whose runner is pytest itself, mapping one criterion to one selector."""
    fixture = dict(
        story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", "")
                   .replace("shows-nothing-when-empty", criterion),
        tests=f"# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
              f"| {criterion} | {selector} |\n",
        profile=PYTEST_PROFILE.format(python=sys.executable.replace("\\", "/")),
        extra_sources=(("tests/test_widgets.py", PYTEST_MODULE),
                       ("pytest.ini", "[pytest]\ntestpaths = tests\n")),
    )
    fixture.update(more)
    return fixture


#: A decision record — the question a stage may not answer, kept where an answer can land.
DECISION = """---
id: STORY-1-01
story: STORY-1
stage: plan
asked: 2026-09-22T20:40:00Z
---

# Does an archived thing count?

## Question
The criteria say "the thing"; the glossary knows archived things. Which the reader sees decides
the read model.

## Options
- a: archived things are shown, marked
- b: archived things are hidden

## Recommendation
b — the story's intent is what the reader needs now.
"""

ANSWER = """
## Answer
answer: b
by: the-expert
at: 2026-09-22T21:00:00Z
rationale: archived is history, not inventory.
"""

PLAN_ASKING = """# Plan — STORY-1

## Context
## Changes
## Acceptance criteria

## needs-human
decision: STORY-1-01
Does an archived thing count? See the record.
"""

PLAN_APPLIED = """# Plan — STORY-1

## Context
Decision STORY-1-01 answered b: archived things are hidden — the read model filters them.
## Changes
## Acceptance criteria
"""


#: A judge's story conflict whose answer lands in the test stage.
CONFLICT = DECISION.replace("stage: plan", "stage: test").replace(
    "# Does an archived thing count?", "# May the agreed test of shows-the-thing change?")
JUDGE_CONFLICT = """# Judge — STORY-1

## Verdict
verdict: story-conflict

## needs-human
decision: STORY-1-01
The judge asks whether an agreed expectation may change; the test stage applies the answer.
"""
PRODUCT = """# Widgets

## What and for whom

A page that shows the things a person has recorded.

## Surfaces

One web page, desktop and phone.

## How it works

The server keeps the things; the page reads them.

## Look and feel

Plain, readable, the project's own stylesheet.

## Qualities

No accounts; one person per installation.

## Not part of the product

Sharing things with others.
"""
TESTS_ON_DECISION = TESTS + "\nDecision STORY-1-01 answered b: the expectation of shows-the-thing changed.\n"


def with_decisions(*records, plan=None, **more):
    """A fixture with decision records under .agents/factory/decisions/ and, optionally, a plan."""
    sources = [(f".agents/factory/decisions/{name}.md", text) for name, text in records]
    if plan is not None:
        sources.append(("tasks/STORY-1/plan.md", plan))
    fixture = dict(extra_sources=tuple(sources))
    fixture.update(more)
    return fixture


#: A whole suite, as `./gradlew test` or `dotnet test` runs one: it writes a JUnit report of what it
#: executed. It fails while `src/state` says `broken`, and writes no report at all — a runner that
#: matched nothing — while `src/state` says `empty`.
SUITE_STUB = """#!/bin/sh
state=$(cat src/state 2>/dev/null)
[ "$state" = empty ] && { echo "no tests matched"; exit 0; }
mkdir -p build/test-results/suite
if [ "$state" = broken ]; then
  printf '<testsuite name="Suite"><testcase classname="Suite" name="holds"><failure>no</failure></testcase></testsuite>\\n' > build/test-results/suite/TEST-Suite.xml
  echo "1 test, 1 failed"; exit 1
fi
printf '<testsuite name="Suite"><testcase classname="Suite" name="holds"/></testsuite>\\n' > build/test-results/suite/TEST-Suite.xml
echo "1 test, 0 failed"
"""


def change_project(root, profile, state="fixed", repository=False):
    """A project for the change check: the suite stub, its state file, optionally committed."""
    build_project(root, tests=None, profile=profile,
                  extra_sources=(("suite.sh", SUITE_STUB), ("src/state", state + "\n"),
                                 (".gitignore", "build/\n")))
    if repository:
        for command in (["init", "-q"], ["add", "-A"],
                        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
    return root


def run_change(gate, root, *args):
    completed = subprocess.run([sys.executable, gate, "--change", *args], cwd=root, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
    return completed.returncode, completed.stdout + completed.stderr


def write_file(root, path, content):
    os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
    with open(os.path.join(root, path), "w", encoding="utf-8") as handle:
        handle.write(content)


#: A scenario contract: two mandatory scenarios, one bound to a configuration. A title may hold a dot.
SCENARIOS = """# Scenarios

## scenario.thing.shown
Title: The reader sees the thing
Runs: always

## scenario.thing.empty
Title: An empty list shows v1.0 of nothing
Runs: always

## scenario.thing.embedded
Title: The thing shows inside a frame
Runs: embedded
"""


def junit(*cases):
    """A JUnit report with `(name, outcome)` cases."""
    body = "".join(
        f'<testcase classname="X" name="{name}"/>' if outcome == "passed" else
        f'<testcase classname="X" name="{name}"><{"skipped" if outcome == "skipped" else "failure"}/></testcase>'
        for name, outcome in cases)
    return f'<testsuite name="X">{body}</testsuite>\n'


def trx(*cases):
    body = "".join(f'<UnitTestResult testName="{name}" outcome="{outcome}"/>' for name, outcome in cases)
    return ('<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010"><Results>'
            f'{body}</Results></TestRun>\n')


def story(story_id, depends_on=(), status="approved"):
    """Another story like STORY-1, with its own id, dependencies and status."""
    return (STORY.replace("STORY-1", story_id)
            .replace("depends_on: []", f"depends_on: [{', '.join(depends_on)}]")
            .replace("status: approved", f"status: {status}"))


def backlog_project(root, *stories, **more):
    """A fixture backlog: STORY-1 plus `(id, depends_on)` stories, no stage file, a profile whose
    only command is `compile: true` — the gates then check files and records, not test runs, so a
    stand-in tool can take several stories through every stage."""
    sources = [(f"backlog/sample/{sid}.md", story(sid, deps)) for sid, deps in stories]
    build_project(root, tests=None, profile="compile: true\n",
                  extra_sources=tuple(sources) + tuple(more.pop("extra_sources", ())), **more)
    return root


def schedule_of(gate, root):
    """{story: (state, from)} and the `next:` / `wait:` lines of `story-gate.py --schedule`."""
    listing = subprocess.run([sys.executable, gate, "--schedule"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
    rows, nxt, wait = {}, "", ""
    for line in listing.stdout.splitlines():
        if line.startswith("next: "):
            nxt = line[6:]
        elif line.startswith("wait: "):
            wait = line[6:]
        elif line and not line.startswith("schedule:"):
            parts = line.split()
            rows[parts[0]] = (parts[1], parts[3] if len(parts) > 3 and parts[2] == "from" else None)
    return rows, nxt, wait, listing.stdout + listing.stderr


DOCUMENT = """# Document — STORY-1

## Glossary

| Term | Context | Added or changed | Definition source |
|---|---|---|---|
| Thing | Widgets | added | `docs/context-map.md:3` — the context's own description |

## Documents updated

| File | What changed | Verified by |
|---|---|---|
| `README.md` | one sentence about the thing | read `README.md:1` |
"""


class Case:
    """One expectation about the gate: which checks must pass, fail or be skipped."""

    def __init__(self, name, stage, expect_exit, must_pass=(), must_fail=(), must_skip=(), text=()):
        self.name = name
        self.stage = stage
        self.expect_exit = expect_exit
        self.must_pass = must_pass
        self.must_fail = must_fail
        self.must_skip = must_skip
        self.text = text


def build_project(root, *, epic=EPIC, story=STORY, tests=TESTS, profile=PROFILE,
                  context_map="# Context map\n\n| Context |\n|---|\n| Widgets |\n",
                  document=None, green=(), rounds=None, ledger=None, extra_sources=()):
    """A project just large enough for the gate to have something to check."""
    def write(path, content):
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    write("backlog/sample/epic.md", epic)
    write("backlog/sample/STORY-1.md", story)
    write(".agents/factory/factory.profile.yaml", profile)
    write("AGENTS.md", "# AGENTS.md\n\nA fixture.\n")
    write("README.md", "A fixture project.\n")
    if context_map is not None:
        write("docs/context-map.md", context_map)
    write("src/test/java/com/example/WidgetUnitTest.java",
          "class WidgetUnitTest { void showsNothingWhenEmpty() {} }\n")
    write("src/test-pages/java/com/example/WidgetPageTest.java",
          "class WidgetPageTest { void showsTheThing() {} }\n")
    for path, content in extra_sources:
        write(path, content)
    if tests is not None:
        write("tasks/STORY-1/tests.md", tests)
    if document is not None:
        write("tasks/STORY-1/document.md", document)
    if rounds is not None:
        write("tasks/STORY-1/.rounds", str(rounds))
    if ledger is not None:
        write("tasks/STORY-1/.tests-red", "\n".join(ledger) + "\n")
    write("runner.sh", RUNNER_STUB)
    os.chmod(os.path.join(root, "runner.sh"), 0o755)
    write("gradlew-stub", TASK_RUNNER_STUB)
    os.chmod(os.path.join(root, "gradlew-stub"), 0o755)
    for selector in green:
        write("green/" + re.sub(r"[./#]", "", selector), "")
    return root


def run_gate(gate, root, stage):
    result = subprocess.run(
        [sys.executable, gate, "--story", "STORY-1", "--stage", stage],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout + result.stderr


def checks_by_verdict(output):
    found = {"pass": set(), "fail": set(), "skip": set(), "note": set()}
    for line in output.splitlines():
        match = re.match(r"gate:(pass|fail|skip|note)\s+(\S+)", line.strip())
        if match:
            found[match.group(1)].add(match.group(2))
    return found




# --- the runner's shape ------------------------------------------------------
# The runner is bash, so these cases call it rather than importing anything: the stage order, the
# artefact names, the verdict handling and the two shapes `install` may leave behind.


_OBSERVE = None


def observe_snapshot(path):
    """Read a tree snapshot with the *observer's* own function, not a copy of its rule here.

    What matters is that `observe.py` refuses to compare a snapshot the runner wrote without a hash
    command; a second implementation of that rule in this file could agree while the observer does
    not, which is the one outcome a check may not have.
    """
    global _OBSERVE
    if _OBSERVE is None:
        spec = importlib.util.spec_from_file_location(
            "factory_observe", os.path.join(HERE, "observe.py"))
        _OBSERVE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_OBSERVE)
    return _OBSERVE.snapshot(path)


def read_snapshot(path):
    """The runner's tree snapshot: digest and path per line."""
    entries = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                parts = line.split("  ", 1)
                if len(parts) == 2:
                    entries[parts[1].strip()] = parts[0].strip()
    except OSError:
        pass
    return entries

def run_runner(runner, root, *args, env=None):
    environment = dict(os.environ)
    environment.update(env or {})
    result = subprocess.run(
        [BASH, runner, *args], cwd=root, capture_output=True, text=True, env=environment,
        encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout + result.stderr


def verify_runner(runner, verbose=False):
    """Order, names, verdicts, links — everything about the runner that holds without a model."""
    results = []
    both_green = ["com.example.WidgetPageTest#showsTheThing",
                  "com.example.WidgetUnitTest#showsNothingWhenEmpty"]

    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok and detail:
            print(f"          {detail}")

    # 1. the stage order, and which gate runs before its stage and which after
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        order = [line.strip()[3:].split("  (")[0].strip()
                 for line in output.splitlines() if line.startswith("── ")]
        expected = ["gate plan", "stage plan", "stage test", "gate test", "stage build",
                    "gate build", "stage tidy", "gate tidy", "stage judge", "stage document",
                    "gate document"]
        check("runner: the plan gate runs before its stage, every other gate after it",
              order == expected, f"got {order}")
        check("runner: a dry run changes nothing", code == 0 and not os.path.isdir(os.path.join(root, "tasks", "STORY-1", "plan.md")))

    # 1a. the stage process sees only the project: the isolation flags, one prefix for every stage
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        flags = [line.split("tool flags:", 1)[1].strip() for line in output.splitlines() if "tool flags:" in line]
        wanted = ("--setting-sources project", "--strict-mcp-config", "--tools Read,Write,Edit,Glob,Grep,Bash,Skill",
                  "--exclude-dynamic-system-prompt-sections")
        check("isolation: a Claude stage runs with the project's settings only, no MCP, the stage tools and no "
              "per-machine system prompt", bool(flags) and all(w in flags[0] for w in wanted), flags[:1])
        check("isolation: every stage gets the same flags, so the prompt prefix is shared across stages",
              len(flags) == 6 and len(set(flags)) == 1, flags)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                                  env=dict(os.environ, FACTORY_ISOLATION="off"))
        flags = [line.split("tool flags:", 1)[1].strip() for line in output.splitlines() if "tool flags:" in line]
        check("isolation: FACTORY_ISOLATION=off drops the flags and the run says so",
              flags and not any(w.split()[0] in flags[0] for w in wanted) and "FACTORY_ISOLATION=off" in output,
              flags[:1])
    with tmpdir() as root:
        build_project(root, profile=PROFILE + "carrier.build: no-such-craft\n")
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("isolation: a carrier the project does not hold stops the run before the first stage, named",
              code == 2 and "no-such-craft" in output and "── stage" not in output, output[-300:])
    # a model per stage: the one flag it becomes, per tool, and who wins against the person's own flags
    def models_of(output):
        rows, stage = {}, None
        for line in output.splitlines():
            if line.startswith("── stage "):
                stage = line.split()[2]
            elif line.strip().startswith("model:") and stage:
                rows[stage] = line.strip()[len("model:"):].strip()
        return rows
    with tmpdir() as root:
        build_project(root, profile=PROFILE + "model.claude.tidy: model-a\nmodel.codex.tidy: model-c\n")
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        rows = models_of(output)
        check("model: `model.claude.tidy` becomes exactly one --model on the tidy stage, and no other stage gets one",
              rows.get("tidy") == "--model model-a" and all(rows.get(s) == "" for s in
                                                              ("plan", "test", "build", "judge", "document")), rows)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "codex", "--dry-run")
        rows = models_of(output)
        check("model: the same profile run with Codex passes only Codex's own key",
              rows.get("tidy") == "-m model-c" and rows.get("build") == "", rows)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "opencode", "--dry-run")
        check("model: a tool without a key in the profile gets no model flag and no complaint",
              all(v == "" for v in models_of(output).values()) and "not applied" not in output, models_of(output))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                                  env=dict(os.environ, FACTORY_CLAUDE_ARGS="--model model-z"))
        check("model: a --model in FACTORY_CLAUDE_ARGS wins over the profile, and the run says so",
              "overridden by FACTORY_CLAUDE_ARGS (model-z)" in models_of(output).get("tidy", ""), models_of(output))
    with tmpdir() as root:
        build_project(root, profile=PROFILE + "model.claude: model-b\n")
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("model: `model.<tool>` is the default for every stage without a key of its own",
              set(models_of(output).values()) == {"--model model-b"} and len(models_of(output)) == 6,
              models_of(output))
    with tmpdir() as root:
        build_project(root, profile=PROFILE.replace("contract: 6", "") + "contract: 99\n")
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "build", "--tool", "claude",
                                  "--dry-run")
        check("contract: a profile newer than the gate stops the run before the first stage, also --from a later one",
              code == 2 and "── stage" not in output and "contract" in output, output[-300:])
    # no model name lives in the pipeline itself
    pipeline_dir = os.path.dirname(os.path.dirname(runner))
    named = []
    for folder, _, names in os.walk(os.path.dirname(pipeline_dir)):
        for name in names:
            if name.endswith(("SKILL.md", ".sh", ".py", ".tmpl")) and "factory-verify" not in folder:
                with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as handle:
                    if re.search(r"\b(opus|sonnet|haiku|gpt-\d|qwen|gemma)\b", handle.read(), re.I):
                        named.append(name)
    check("model: no model name in the runner, the gate, a template or a skill", not named, named)

    # an OpenCode invocation's usage, from the events `opencode run --format json` writes
    with tmpdir() as root:
        raw = os.path.join(root, "stage.out")
        with open(raw, "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(e) for e in [
                {"type": "step_start", "part": {"type": "step-start"}},
                {"type": "text", "part": {"type": "text", "text": "the plan is written"}},
                {"type": "step_finish", "part": {"type": "step-finish", "cost": 0, "tokens": {
                    "total": 12123, "input": 11773, "output": 4, "reasoning": 346, "cache": {"write": 0, "read": 0}}}},
                {"type": "step_finish", "part": {"type": "step-finish", "cost": 0, "tokens": {
                    "input": 200, "output": 50, "reasoning": 0, "cache": {"write": 0, "read": 11700}}}}]) + "\n")
        gate = os.path.join(os.path.dirname(runner), "story-gate.py")
        read = subprocess.run([sys.executable, gate, "--usage-from", "opencode-json", raw, "--usage-model",
                               "lmstudio-local/some-model"], capture_output=True, text=True, encoding="utf-8").stdout
        check("opencode: usage is read from the step_finish events, a local model has no price, the answer is shown",
              read.splitlines()[:1] == ["model=lmstudio-local/some-model\tinput=11973\tcache_read=11700\tcache_write=0\toutput=400"]
              and "the plan is written" in read, read)

    # 1b. a whole run without a model: the loop, the journal and the final report
    # FACTORY_TOOL_CMD stands in for the tool and writes each stage's artefact, so a defect in the
    # loop — a stage silently skipped, a report naming stages that never ran — fails here rather
    # than after an hour of real work.
    stand_in = (
        'case "$FACTORY_STAGE" in '
        'test) f=tests.md ;; *) f="$FACTORY_STAGE.md" ;; esac; '
        'mkdir -p tasks/STORY-1; '
        'case "$FACTORY_STAGE" in '
        '  plan) printf "## Context\\n## Changes\\n## Acceptance criteria\\n" ;; '
        '  test) cat "$FIXTURE_TESTS" ;; '
        '  build) printf "## Changed\\n## Criteria\\n## Checks\\n## Files\\n"; '
        '    for s in $(cat "$FIXTURE_GREEN" 2>/dev/null); do printf -- "- green/%s\\n" "$s"; done ;; '
        '  tidy) printf "## Moves\\n## Checks\\n## Files\\n" ;; '
        '  judge) printf "## Verdict\\nverdict: pass\\n" ;; '
        '  document) printf "## Glossary\\n" ;; '
        'esac > "tasks/STORY-1/$f"; '
        # red until the build stage, as a real run is: the test gate must see them fail
        'case "$FACTORY_STAGE" in build|tidy|judge|document) '
        '  for s in $(cat "$FIXTURE_GREEN" 2>/dev/null); do mkdir -p green; : > "green/$s"; done ;; '
        'esac'
    )
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        # the stand-in turns the mapped tests green from the build stage onwards
        with open(os.path.join(root, "greens.txt"), "w", encoding="utf-8") as handle:
            handle.write("")
        tests_path = os.path.join(root, "fixture-tests.md")
        with open(tests_path, "w", encoding="utf-8") as handle:
            handle.write(TESTS)
        os.remove(os.path.join(root, "tasks", "STORY-1", "tests.md"))
        greens = " ".join(re.sub(r"[./#]", "", s) for s in both_green)
        with open(os.path.join(root, "greens.txt"), "w", encoding="utf-8") as handle:
            handle.write(greens + "\n")
        env = {"FACTORY_TOOL_CMD": stand_in, "FIXTURE_TESTS": shell_path(tests_path),
               "FIXTURE_GREEN": shell_path(os.path.join(root, "greens.txt"))}
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env=env)
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: every stage runs, in order, in a real run",
              stages == ["plan", "test", "build", "tidy", "judge", "document"],
              f"stages that ran: {stages}; the run's last lines:\n"
              + "\n".join("            " + l for l in output.strip().splitlines()[-14:]))
        check("runner: the final line names the stages that ran",
              "ran through plan,test,build,tidy,judge,document." in output,
              [l for l in output.splitlines() if "ran through" in l])
        journal = os.path.join(root, "tasks", "STORY-1", ".verify")
        kept = os.listdir(journal) if os.path.isdir(journal) else []     # absent when nothing ran
        check("runner: the journal records a start and an end per stage",
              os.path.isfile(os.path.join(journal, "journal.tsv"))
              and open(os.path.join(journal, "journal.tsv"), encoding="utf-8").read().count("stage-end") == 6)
        check("runner: a tree snapshot is kept around every stage",
              len([f for f in kept if f.startswith("tree-")]) == 12)
        check("runner: every gate run is kept, not only a refusal",
              len([f for f in kept if f.startswith("gate-")]) >= 4)

    # 1b'. --shared-builder: plan to tidy in one process, gated by it and re-checked by the runner
    builder_cmd = ('if [ "$FACTORY_STAGE" = builder ]; then for s in plan test build tidy; do '
                   'FACTORY_STAGE=$s sh -c "$FIXTURE_STAND_IN"; '
                   'if [ "$s" = test ] && [ -z "${FIXTURE_SKIP_TEST_GATE:-}" ]; then '
                   '"$FIXTURE_PY" .agents/factory/story-gate.py --story STORY-1 --stage test >/dev/null; fi; done; '
                   'else sh -c "$FIXTURE_STAND_IN"; fi')
    def shared_run(skip_test_gate=False, dry=False):
        with tmpdir() as root:
            build_project(root)
            shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                        os.path.join(root, ".agents", "factory", "story-gate.py"))
            tests_path = os.path.join(root, "fixture-tests.md")
            with open(tests_path, "w", encoding="utf-8") as handle:
                handle.write(TESTS)
            os.remove(os.path.join(root, "tasks", "STORY-1", "tests.md"))
            with open(os.path.join(root, "greens.txt"), "w", encoding="utf-8") as handle:
                handle.write(" ".join(re.sub(r"[./#]", "", s) for s in both_green) + "\n")
            env = {"FACTORY_TOOL_CMD": builder_cmd, "FIXTURE_STAND_IN": stand_in,
                   "FIXTURE_TESTS": shell_path(tests_path), "FIXTURE_PY": shell_path(sys.executable),
                   "FIXTURE_GREEN": shell_path(os.path.join(root, "greens.txt"))}
            if skip_test_gate:
                env["FIXTURE_SKIP_TEST_GATE"] = "1"
            args = ["run", "--story", "STORY-1", "--tool", "stand-in", "--shared-builder"] + (["--dry-run"] if dry else [])
            code, output = run_runner(runner, root, *args, env=env)
            journal = os.path.join(root, "tasks", "STORY-1", ".verify", "journal.tsv")
            starts = [l.split("\t")[2] for l in open(journal, encoding="utf-8").read().splitlines()
                      if "\tstage-start\t" in l] if os.path.isfile(journal) else []
            delivered = os.path.isfile(os.path.join(root, "tasks", "STORY-1", ".delivered"))
            return code, output, starts, delivered
    code, output, starts, delivered = shared_run()
    stage_lines = [l.split("  (")[0][3:] for l in output.splitlines() if l.startswith("── stage ")]
    check("shared builder: plan to tidy run as one process, then judge and document each in their own",
          code == 0 and starts == ["builder", "judge", "document"] and delivered
          and stage_lines == ["stage plan+test+build+tidy", "stage judge", "stage document"]
          and "ran through plan,test,build,tidy,judge,document." in output,
          f"exit {code}; starts {starts}; {stage_lines}; {output.strip().splitlines()[-3:]}")
    check("shared builder: the runner re-checks the build and tidy gates itself",
          "── gate build  (re-checked by the runner)" in output and "── gate tidy  (re-checked by the runner)" in output,
          [l for l in output.splitlines() if l.startswith("── gate")])
    code, output, starts, delivered = shared_run(skip_test_gate=True)
    check("shared builder: a process that never ran the test gate is caught — no red proof, no judge",
          code == 1 and "no red proof" in output and "judge" not in starts and not delivered,
          f"exit {code}; starts {starts}; {output.strip().splitlines()[-2:]}")
    code, output, starts, delivered = shared_run(dry=True)
    check("shared builder: the dry run shows the one shared invocation and starts nothing",
          "stage plan+test+build+tidy  (tool: stand-in, one shared context)" in output and starts == [],
          [l for l in output.splitlines() if l.startswith("── stage")])

    # 1c. a stage that writes no file stops the run, and says which file was missing
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "true"})
        check("runner: a stage that produced no file stops the run",
              code != 0 and "produced no tasks/STORY-1/plan.md" in output,
              output.strip().splitlines()[-1] if output.strip() else "no output")

    # 1d. a stage that escalates stops the run
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        escalating = ('mkdir -p tasks/STORY-1; printf "## Context\\n## Changes\\n'
                      '## Acceptance criteria\\n## needs-human\\nSomeone must decide.\\n" '
                      '> tasks/STORY-1/plan.md')
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": escalating})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: a stage that ends with needs-human stops the run",
              code != 0 and stages == ["plan"] and "needs-human" in output,
              f"stages that ran: {stages}, exit {code}")

    # 1d1. a bare needs-human heading from the template is not an escalation
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        bare = ('mkdir -p tasks/STORY-1; printf "## Context\\n## Changes\\n'
                '## Acceptance criteria\\n## needs-human\\n(none)\\n" > tasks/STORY-1/plan.md')
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": bare})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: an empty needs-human heading does not stop the run",
              stages[:2] == ["plan", "test"] and "ends with a needs-human section" not in output,
              f"stages that ran: {stages}")
        bare = bare.replace("(none)", "None.")
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": bare})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: a needs-human heading that says `None.` does not stop the run",
              stages[:2] == ["plan", "test"] and "ends with a needs-human section" not in output,
              f"stages that ran: {stages}")

    # 1d2. a stage that asks writes the record; the run names it and how to resume
    with tmpdir() as root:
        build_project(root)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        asking = ('mkdir -p tasks/STORY-1 .agents/factory/decisions; '
                  'cat "$FIXTURE_DECISION" > .agents/factory/decisions/STORY-1-01.md; '
                  'cat "$FIXTURE_PLAN" > tasks/STORY-1/plan.md')
        with open(os.path.join(root, "decision.md"), "w", encoding="utf-8") as handle:
            handle.write(DECISION)
        with open(os.path.join(root, "plan.md"), "w", encoding="utf-8") as handle:
            handle.write(PLAN_ASKING)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": asking,
                                       "FIXTURE_DECISION": shell_path(os.path.join(root, "decision.md")),
                                       "FIXTURE_PLAN": shell_path(os.path.join(root, "plan.md"))})
        check("runner: a stage that asks a question names the record and the command that resumes",
              code == 3 and ".agents/factory/decisions/STORY-1-01.md" in output
              and "--from plan" in output,
              [l for l in output.splitlines() if "decision" in l][:3])
        # and with the question still open, the next run does not start a stage
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  "--from", "test", env={"FACTORY_TOOL_CMD": "true"})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: while a question is open no stage runs, whatever --from says",
              code == 3 and stages == [] and "waits for a decision" in output,
              f"stages that ran: {stages}")

    # 1e. install keeps what the project owns
    source = shell_path(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")))
    # 1e'. a project that already drives a browser gets that command and `browser: playwright` in its profile
    with tmpdir() as root:
        for path, text in (("build.gradle", "plugins { id 'java' }\napply from: \"gradle/plugins/test-e2e.gradle\"\n"),
                           ("gradle/plugins/test-e2e.gradle", "dependencies { testE2eImplementation 'com.microsoft.playwright:playwright:1.62.0' }\n")):
            os.makedirs(os.path.dirname(os.path.join(root, path)) or root, exist_ok=True)
            with open(os.path.join(root, path), "w", encoding="utf-8") as handle:
                handle.write(text)
        run_runner(runner, root, "install", "--tool", "claude", "--from", source, "--copy")
        profile_text = open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), encoding="utf-8").read() \
            if os.path.isfile(os.path.join(root, ".agents", "factory", "factory.profile.yaml")) else ""
        check("install: a Playwright setup it finds becomes the end-user command and `browser: playwright`",
              "e2eTest: ./gradlew test-e2e" in profile_text and "\nbrowser: playwright" in profile_text,
              [l for l in profile_text.splitlines() if l.startswith(("e2eTest", "browser"))])
    # 1d'. the carriers a profile names reach Claude's own skill directory, and only those
    carrier = next((name for name in ("ddd-modelling", "review-craft", "e2e-testing")
                    if any(os.path.isdir(os.path.join(plugins_dir, plugin, "skills", name))
                           for plugin in os.listdir(plugins_dir))), None) \
        if os.path.isdir(plugins_dir := os.path.dirname(os.path.dirname(source))) else None
    if carrier:
        with tmpdir() as root:
            build_project(root, profile=PROFILE + f"carrier.build: {carrier}\n")
            code, output = run_runner(runner, root, "install", "--tool", "claude", "--from", source)
            skills_dir = os.path.join(root, ".claude", "skills")
            # skill folders only: a copying install (no symlinks, as on Windows) keeps its list beside them
            entries = sorted(e for e in os.listdir(skills_dir) if not e.startswith(".")) if os.path.isdir(skills_dir) else []
            check("install: a carrier the profile names is placed in .claude/skills beside the pipeline, "
                  "no other craft skill", os.path.isdir(skills_dir) and not os.path.islink(skills_dir)
                  and os.path.isfile(os.path.join(skills_dir, carrier, "SKILL.md"))
                  and "factory-run" in entries and len(entries) == 14,
                  f"exit {code}; {entries}")
            code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
            check("install: after it, the runner's carrier check passes", code == 0 and "── stage plan" in output,
                  output[-200:])
    with tmpdir() as root:
        build_project(root)
        own = os.path.join(root, ".codex", "skills", "our-own-skill")
        os.makedirs(own)
        with open(os.path.join(own, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write("---\nname: our-own-skill\ndescription: the project's own\n---\n")
        stale = os.path.join(root, ".codex", "skills", "gone-from-the-source")
        if SYMLINKS:
            os.symlink(os.path.join(source, "no-longer-here"), stale)
        run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        entries = os.listdir(os.path.join(root, ".codex", "skills"))
        check("install: a skill the project owns survives the install",
              "our-own-skill" in entries and
              os.path.isfile(os.path.join(own, "SKILL.md")),
              f"{sorted(entries)[:5]}…")
        if SYMLINKS:
            check("install: a link whose skill is gone from the source is pruned",
                  "gone-from-the-source" not in entries)
    if SYMLINKS:
        with tmpdir() as root:
            build_project(root)
            skills = os.path.join(root, ".codex", "skills")
            os.makedirs(skills)
            elsewhere = os.path.join(root, "our-stage-plan")
            os.makedirs(elsewhere)
            with open(os.path.join(elsewhere, "SKILL.md"), "w", encoding="utf-8") as handle:
                handle.write("---\nname: stage-plan\ndescription: the project's own plan stage\n---\n")
            os.symlink(elsewhere, os.path.join(skills, "stage-plan"))
            run_runner(runner, root, "install", "--tool", "codex", "--from", source)
            check("install: a link the *project* made is not replaced either",
                  os.path.realpath(os.path.join(skills, "stage-plan")) == os.path.realpath(elsewhere),
                  f"stage-plan now points at {os.path.realpath(os.path.join(skills, 'stage-plan'))}")
    else:
        print("  skip  install: the two link cases — this account cannot create symlinks, so install copies")

    # 1g. a backlog run: story after story, past a question, and back to it once it is answered.
    # The stand-in writes each stage's file; STORY-1's plan stage asks until its record is answered.
    stand_in_backlog = """#!/bin/sh
echo "$FACTORY_STORY $FACTORY_STAGE" >> invocations.log
d="tasks/$FACTORY_STORY"; rec=.agents/factory/decisions/STORY-1-01.md
mkdir -p "$d" .agents/factory/decisions
case "$FACTORY_STAGE" in
  plan)
    if [ "$FACTORY_STORY" = STORY-1 ] && ! grep -q '^## Answer' "$rec" 2>/dev/null; then
      cat fixture/decision.md > "$rec"; cat fixture/plan-asking.md > "$d/plan.md"
    elif [ "$FACTORY_STORY" = STORY-1 ]; then cat fixture/plan-applied.md > "$d/plan.md"
    else printf '## Context\\n## Changes\\n## Acceptance criteria\\n' > "$d/plan.md"; fi ;;
  test) cat fixture/tests.md > "$d/tests.md" ;;
  build) printf '## Changed\\n\\n## Files\\n' > "$d/build.md" ;;
  tidy) printf '## Moves\\n\\n## Files\\n' > "$d/tidy.md" ;;
  judge) printf '## Verdict\\nverdict: pass\\n' > "$d/judge.md" ;;
  document) printf '## Glossary\\n' > "$d/document.md" ;;
esac
[ -n "${FIXTURE_USAGE:-}" ] && printf '%s' "$FIXTURE_USAGE"
exit 0
"""

    def backlog_fixture(root):
        backlog_project(root, ("STORY-2", []), ("STORY-3", ["STORY-1"]),
                        extra_sources=(("fixture/decision.md", DECISION),
                                       ("fixture/plan-asking.md", PLAN_ASKING),
                                       ("fixture/plan-applied.md", PLAN_APPLIED),
                                       ("fixture/tests.md", TESTS),
                                       # the stand-in's own log is not the story's change
                                       (".gitignore", "invocations.log\n")))
        # LF on every platform: a shell script with CRLF endings is not the script it looks like
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in_backlog)
        shutil.copy(os.path.join(os.path.dirname(runner), "story-gate.py"),
                    os.path.join(root, ".agents", "factory", "story-gate.py"))
        return {"FACTORY_TOOL_CMD": "sh stand-in.sh"}

    def invocations(root):
        path = os.path.join(root, "invocations.log")
        return open(path, encoding="utf-8").read().split("\n")[:-1] if os.path.isfile(path) else []

    def answer(root):
        with open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"), "a",
                  encoding="utf-8") as handle:
            handle.write(ANSWER)

    six = ["plan", "test", "build", "tidy", "judge", "document"]
    with tmpdir() as root:
        env = backlog_fixture(root)
        code, output = run_runner(runner, root, "backlog", env=env)
        ran = invocations(root)
        check("backlog: a story that asks at its plan stage does not stop the stories that do not need it",
              code == 0 and ran == ["STORY-1 plan"] + [f"STORY-2 {s}" for s in six],
              f"exit {code}, invocations {ran}, last lines: {output.strip().splitlines()[-3:]}")
        check("backlog: the story that depends on the waiting one stays blocked",
              "STORY-3  blocked" in output, [l for l in output.splitlines() if "STORY-3" in l])
        answer(root)
        code, output = run_runner(runner, root, "backlog", env=env)
        ran = invocations(root)[7:]
        check("backlog: after the answer the story resumes at the stage that asked, then its dependant runs",
              code == 0 and ran == [f"STORY-1 {s}" for s in six] + [f"STORY-3 {s}" for s in six],
              f"exit {code}, invocations {ran}, last lines: {output.strip().splitlines()[-4:]}")
        record = open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"),
                      encoding="utf-8").read()
        check("backlog: the resumed stage's answer is stamped applied", "## Applied" in record)
        code, output = run_runner(runner, root, "backlog", env=env)
        check("backlog: with everything delivered a run invokes nothing",
              code == 0 and len(invocations(root)) == 19 and "nothing more can run" in output,
              f"exit {code}, {len(invocations(root))} invocations")

    # 1h. --watch: waits on the answer without invoking anything, then picks the story up itself
    with tmpdir() as root:
        env = backlog_fixture(root)
        environment = dict(os.environ)
        environment.update(env)
        log_path = os.path.join(root, "watch.log")
        with open(log_path, "w", encoding="utf-8") as log:
            process = subprocess.Popen([BASH, runner, "backlog", "--watch", "--interval", "1"],
                                       cwd=root, stdout=log, stderr=subprocess.STDOUT, env=environment)
            deadline = time.time() + 60
            while time.time() < deadline and "waiting for an answer" not in open(
                    log_path, encoding="utf-8", errors="replace").read():
                time.sleep(0.2)
            idle_before = len(invocations(root))
            time.sleep(3)                             # three polls at least
            idle_after = len(invocations(root))
            answer(root)
            try:
                code = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                code = "timeout"
        output = open(log_path, encoding="utf-8", errors="replace").read()
        check("watch: waiting for an answer invokes no agent",
              idle_before == 7 and idle_after == idle_before,
              f"{idle_before} invocations when the wait began, {idle_after} three seconds later")
        check("watch: a confirmed answer is picked up without anyone restarting the story",
              code == 0 and len(invocations(root)) == 19 and "nothing waits on an answer" in output,
              f"exit {code}, {len(invocations(root))} invocations, last lines: {output.strip().splitlines()[-3:]}")

    # 1i. the limits: --max-stages stops dispatch and keeps the work, the stop file ends a run
    with tmpdir() as root:
        env = backlog_fixture(root)
        code, output = run_runner(runner, root, "backlog", "--max-stages", "2", env=env)
        check("backlog: --max-stages stops before the next invocation and keeps what ran",
              code == 4 and invocations(root) == ["STORY-1 plan", "STORY-2 plan"]
              and os.path.isfile(os.path.join(root, "tasks", "STORY-2", "plan.md")),
              f"exit {code}, invocations {invocations(root)}")
    with tmpdir() as root:
        env = backlog_fixture(root)
        open(os.path.join(root, ".agents", "factory", "stop"), "w").close()
        code, output = run_runner(runner, root, "backlog", env=env)
        check("backlog: the stop file ends the run before any story starts",
              code == 0 and invocations(root) == [] and "stops here" in output,
              f"exit {code}, invocations {invocations(root)}")

    # 1j. a refused gate after its stage: the stage runs again with the report, one round counted
    with tmpdir() as root:
        env = backlog_fixture(root)
        # the test stage forgets the mapping the first time, and writes it the second
        stand_in = open(os.path.join(root, "stand-in.sh"), encoding="utf-8").read().replace(
            '  test) cat fixture/tests.md > "$d/tests.md" ;;',
            '  test) if [ -f "$d/.forgot" ]; then cat fixture/tests.md > "$d/tests.md"; '
            'else : > "$d/.forgot"; echo "# Tests" > "$d/tests.md"; fi ;;')
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        ran = invocations(root)
        check("runner: a refused gate sends the story back to that stage, one round counted",
              code == 0 and ran.count("STORY-2 test") == 2 and "round 1 runs stage 'test' again" in output
              and open(os.path.join(root, "tasks", "STORY-2", ".rounds"), encoding="utf-8").read().strip() == "1",
              f"exit {code}, invocations {ran}")
    with tmpdir() as root:
        env = backlog_fixture(root)
        stand_in = open(os.path.join(root, "stand-in.sh"), encoding="utf-8").read().replace(
            '  test) cat fixture/tests.md > "$d/tests.md" ;;', '  test) echo "# Tests" > "$d/tests.md" ;;')
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        check("runner: a gate that refuses three rounds stops the story",
              code == 1 and invocations(root).count("STORY-2 test") == 3 and "three rounds did not converge" in output,
              f"exit {code}, invocations {invocations(root)}")

    # 1k. a repeat judge round sees the previous verdict
    with tmpdir() as root:
        env = backlog_fixture(root)
        stand_in = open(os.path.join(root, "stand-in.sh"), encoding="utf-8").read().replace(
            "  judge) printf '## Verdict\\nverdict: pass\\n' > \"$d/judge.md\" ;;",
            "  judge) echo \"$FACTORY_PROMPT\" >> judge-prompts.log; "
            "if [ -f \"$d/.judge-previous.md\" ]; then printf '## Verdict\\nverdict: pass\\n' > \"$d/judge.md\"; "
            "else printf '## Verdict\\nverdict: changes-requested\\n' > \"$d/judge.md\"; fi ;;")
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        prompts = open(os.path.join(root, "judge-prompts.log"), encoding="utf-8").read() \
            if os.path.isfile(os.path.join(root, "judge-prompts.log")) else ""
        check("runner: the judge's repeat round is handed the previous verdict",
              code == 0 and prompts.count("Apply the stage-judge") == 2
              and ".judge-previous.md" in prompts.split("Apply the stage-judge")[2]
              and ".judge-previous.md" not in prompts.split("Apply the stage-judge")[1],
              f"exit {code}; prompts: {prompts[-300:]}")

    # 1m. a judge's story conflict is a question: the run waits, and names the stage that applies it
    with tmpdir() as root:
        env = backlog_fixture(root)
        with open(os.path.join(root, "fixture", "judge-conflict.md"), "w", encoding="utf-8") as handle:
            handle.write(JUDGE_CONFLICT.replace("STORY-1", "STORY-2"))
        with open(os.path.join(root, "fixture", "conflict.md"), "w", encoding="utf-8") as handle:
            handle.write(CONFLICT.replace("STORY-1", "STORY-2"))
        stand_in = open(os.path.join(root, "stand-in.sh"), encoding="utf-8").read().replace(
            "  judge) printf '## Verdict\\nverdict: pass\\n' > \"$d/judge.md\" ;;",
            "  judge) cat fixture/conflict.md > .agents/factory/decisions/STORY-2-01.md; "
            "cat fixture/judge-conflict.md > \"$d/judge.md\" ;;")
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        check("runner: a judge's story conflict with a record waits for the answer at the stage that applies it",
              code == 3 and "--from test" in output, f"exit {code}; {[l for l in output.splitlines() if 'decision' in l][:3]}")

    # 1n. what a stage cost: recorded per invocation, summed per story and stage, bounded per story
    claude_like = ('{"result":"done","total_cost_usd":0.01,"modelUsage":{"some-model":{"inputTokens":100,'
                   '"outputTokens":900,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}}')
    with tmpdir() as root:
        env = backlog_fixture(root)
        env.update({"FIXTURE_USAGE": claude_like, "FACTORY_USAGE_FORMAT": "claude-json"})
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        journal = open(os.path.join(root, "tasks", "STORY-2", ".verify", "journal.tsv"), encoding="utf-8").read()
        report = subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"),
                                 "--usage", "--story", "STORY-2"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        check("usage: each invocation's tokens land in the story's journal",
              code == 0 and journal.count("\tusage\t") == 6 and "output=900" in journal,
              f"exit {code}; usage lines {journal.count(chr(9) + 'usage' + chr(9))}")
        check("usage: the report sums tokens and cost per stage and per story",
              "STORY-2/plan" in report and "STORY-2 total" in report and "5400" in report and "0.06" in report,
              report.strip().splitlines()[-3:])
        check("usage: the stage's final message still reaches the log", "done" in output, output[-200:])
        _, _, _, sched = schedule_of(os.path.join(root, ".agents", "factory", "story-gate.py"), root)
        check("usage: the schedule shows a story's tokens", "6,000 tokens" in sched,
              [l for l in sched.splitlines() if "STORY-2" in l])
    with tmpdir() as root:
        env = backlog_fixture(root)
        env.update({"FIXTURE_USAGE": claude_like, "FACTORY_USAGE_FORMAT": "claude-json"})
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  "--story-budget", "2500", env=env)
        first = len(invocations(root))
        code2, output2 = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                    "--from", "build", "--story-budget", "2500", env=env)
        check("usage: --story-budget stops dispatch once the story has used it, and a restart keeps the count",
              code == 4 and first == 3 and code2 == 4 and len(invocations(root)) == 3
              and "has used 3000 tokens" in output2, f"exit {code}/{code2}, invocations {first}/{len(invocations(root))}")
    with tmpdir() as root:
        env = backlog_fixture(root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        report = subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"),
                                 "--usage", "--story", "STORY-2"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        check("usage: a tool that reports nothing is counted as unknown, never as zero",
              "6 invocation(s) without a usage report" in report, report.strip().splitlines()[-2:])

    # 1l. a resumed document stage whose file already holds is not invoked again
    with tmpdir() as root:
        env = backlog_fixture(root)
        run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        os.remove(os.path.join(root, "tasks", "STORY-2", ".delivered"))
        before = len(invocations(root))
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  "--from", "document", env=env)
        check("runner: a document file that already holds costs no invocation on resume",
              code == 0 and len(invocations(root)) == before and "already holds" in output
              and os.path.isfile(os.path.join(root, "tasks", "STORY-2", ".delivered")),
              f"exit {code}, {len(invocations(root)) - before} new invocation(s)")

    # 1o. update: the newest pipeline, the same tools, links stay links and copies stay copies
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        stamp = os.path.join(root, ".agents", "factory", "gate.installed")
        text = open(stamp, encoding="utf-8").read()
        with open(stamp, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"version: .*", "version: 0.0.1", text))
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("contract: 1\n")
        project_runner = os.path.join(root, ".agents", "factory", "factory.sh")
        code, output = run_runner(project_runner, root, "update", "--from", source)
        entries = os.listdir(os.path.join(root, ".codex", "skills"))
        check("update: run from the project's own runner, it brings the stamp to the pipeline it names",
              code == 0 and "updated 0.0.1 →" in output and "version: 0.0.1" not in open(stamp, encoding="utf-8").read(),
              output.strip().splitlines()[-3:])
        # Without symlinks the install copied in the first place (the probe above), so the update keeps copies.
        kept_kind = os.path.islink(os.path.join(root, ".codex", "skills", "factory-run")) if SYMLINKS else \
            os.path.isdir(os.path.join(root, ".codex", "skills", "factory-run"))
        check("update: a tool keeps how it holds the skills (links, or copies where the shell cannot link), "
              "and no tool is added",
              kept_kind and "factory-run" in entries and not os.path.exists(os.path.join(root, ".opencode")),
              sorted(entries)[:4])
        check("update: an older contract line in the profile is named, and the profile is left alone",
              "raise it to 'contract:" in output
              and "contract: 1" in open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), encoding="utf-8").read(),
              [l for l in output.splitlines() if "contract" in l][:2])
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "claude", "--from", source, "--copy")
        copied = os.path.join(root, ".claude", "skills", "factory-run", "SKILL.md")
        with open(copied, "a", encoding="utf-8") as handle:
            handle.write("\nSTALE COPY\n")
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "update",
                                  "--from", source)
        check("update: copies stay copies, refreshed from the pipeline, and are to be committed",
              code == 0 and os.path.isdir(os.path.join(root, ".claude", "skills", "factory-run"))
              and not os.path.islink(os.path.join(root, ".claude", "skills", "factory-run"))
              and "STALE COPY" not in open(copied, encoding="utf-8").read() and "commit" in output,
              output.strip().splitlines()[-4:])
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        stamp = os.path.join(root, ".agents", "factory", "gate.installed")
        text = open(stamp, encoding="utf-8").read()
        with open(stamp, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"version: .*", "version: 0.0.1", text))
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "status",
                                  env={"FACTORY_PLUGIN_DIR": source})
        check("status: a project behind the pipeline is told so, with the update to run",
              code == 0 and "installed from pipeline 0.0.1" in output, [l for l in output.splitlines() if "pipeline" in l][:2])

    with tmpdir() as root:
        # a newer pipeline with a skill the project's runner never heard of, and its own install step
        newer = os.path.join(root, "newer-plugin")
        shutil.copytree(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")), newer, symlinks=True)
        os.makedirs(os.path.join(newer, "factory-brand-new"))
        with open(os.path.join(newer, "factory-brand-new", "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write("---\nname: factory-brand-new\ndescription: a skill added in a later release\n---\n")
        newer_runner = os.path.join(newer, "factory-run", "scripts", "factory.sh")
        body = open(newer_runner, encoding="utf-8").read().replace(
            '  check_dca_setup\n', '  check_dca_setup\n  : > .agents/factory/added-by-the-newer-install\n', 1)
        with open(newer_runner, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        project = os.path.join(root, "project")
        os.makedirs(project)
        build_project(project)
        run_runner(runner, project, "install", "--tool", "claude", "--from", source, "--copy")
        code, output = run_runner(os.path.join(project, ".agents", "factory", "factory.sh"), project, "update",
                                  "--from", shell_path(newer))
        check("update: a newer pipeline's new skill arrives, and its own install step runs, not the old copy's",
              code == 0 and os.path.isfile(os.path.join(project, ".claude", "skills", "factory-brand-new", "SKILL.md"))
              and os.path.isfile(os.path.join(project, ".agents", "factory", "added-by-the-newer-install")),
              output.strip().splitlines()[-3:])

    with tmpdir() as root:
        # copies: the project's own skills, including one with a pipeline skill's name, survive; a skill
        # the pipeline dropped leaves the copy
        build_project(root)
        skills_dir = os.path.join(root, ".claude", "skills")
        for own in ("our-own-skill", "stage-plan"):
            os.makedirs(os.path.join(skills_dir, own))
            with open(os.path.join(skills_dir, own, "SKILL.md"), "w", encoding="utf-8") as handle:
                handle.write(f"---\nname: {own}\ndescription: the project's own\n---\nOURS\n")
        code, output = run_runner(runner, root, "install", "--tool", "claude", "--from", source, "--copy")
        manifest = open(os.path.join(skills_dir, ".dca-factory-skills"), encoding="utf-8").read().split()
        check("copies: the project's own skills stay, a same-named one is not overwritten, and the list names only "
              "what the pipeline copied",
              "OURS" in open(os.path.join(skills_dir, "stage-plan", "SKILL.md"), encoding="utf-8").read()
              and os.path.isdir(os.path.join(skills_dir, "our-own-skill")) and "factory-run" in manifest
              and "stage-plan" not in manifest and "our-own-skill" not in manifest
              and "kept the project's own .claude/skills/stage-plan" in output, output.strip().splitlines()[-3:])
        dropped = os.path.join(root, "trimmed-plugin")
        shutil.copytree(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")), dropped, symlinks=True)
        shutil.rmtree(os.path.join(dropped, "factory-scope"))
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "update",
                                  "--from", shell_path(dropped))
        check("copies: a skill the pipeline dropped is removed on update; the project's own stay",
              code == 0 and not os.path.exists(os.path.join(skills_dir, "factory-scope"))
              and os.path.isdir(os.path.join(skills_dir, "our-own-skill"))
              and "OURS" in open(os.path.join(skills_dir, "stage-plan", "SKILL.md"), encoding="utf-8").read(),
              [l for l in output.splitlines() if "removed" in l or "kept" in l][:3])

    # 1r. inside an agent session the runner does not start a real tool
    with tmpdir() as root:
        env = backlog_fixture(root)
        nested = dict(os.environ)
        nested.pop("FACTORY_TOOL_CMD", None)
        nested.update({"CLAUDE_CODE_SESSION_ID": "some-session", "PATH": os.environ.get("PATH", "")})
        result = subprocess.run([BASH, runner, "run", "--story", "STORY-2", "--tool", "claude"], cwd=root,
                                capture_output=True, text=True, env=nested, encoding="utf-8", errors="replace")
        check("runner: inside an agent session it refuses a real tool, before any stage",
              result.returncode == 6 and "belongs to an agent session" in result.stderr
              and not os.path.exists(os.path.join(root, "tasks", "STORY-2", "plan.md")),
              f"exit {result.returncode}; {result.stderr.strip().splitlines()[-1:] if result.stderr else ''}")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  env=dict(env, CLAUDE_CODE_SESSION_ID="some-session"))
        check("runner: a stand-in starts no tool and is not refused inside a session",
              code == 0 and len(invocations(root)) == 6, f"exit {code}")

    # 1q. a custom command is handed the stage's model and the journal says it was not applied by the runner
    with tmpdir() as root:
        env = backlog_fixture(root)
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("model.claude.build: model-q\n")
        env = dict(env, FACTORY_TOOL_CMD='echo "$FACTORY_STAGE=$FACTORY_MODEL" >> models.log; sh stand-in.sh')
        with open(os.path.join(root, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("models.log\n")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "claude", env=env)
        seen = open(os.path.join(root, "models.log"), encoding="utf-8").read().split() \
            if os.path.isfile(os.path.join(root, "models.log")) else []
        journal = open(os.path.join(root, "tasks", "STORY-2", ".verify", "journal.tsv"), encoding="utf-8").read() \
            if os.path.isfile(os.path.join(root, "tasks", "STORY-2", ".verify", "journal.tsv")) else ""
        status = subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"), "--status",
                                 "--story", "STORY-2"], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout
        build_row = next((l for l in status.splitlines() if l.startswith("build ")), "")
        check("model: a custom command gets FACTORY_MODEL for its stage only, the journal records the request "
              "as not applied by the runner, and the status says so",
              "build=model-q" in seen and "plan=" in seen
              and "model_requested=model-q\tmodel_applied=no (passed as FACTORY_MODEL" in journal
              and "(requested model-q: not applied)" in build_row,
              f"exit {code}; {seen}; {build_row}")

    # 1p. a runner does not start while another worker holds the checkout
    with tmpdir() as root:
        env = backlog_fixture(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"), "--claim",
                        "claude-session:other"], cwd=root, capture_output=True)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        check("runner: another worker's claim stops it before any stage, and it says who holds the checkout",
              code == 5 and invocations(root) == [] and "held by claude-session:other" in output,
              f"exit {code}; {output.strip().splitlines()[-2:]}")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  env=dict(env, FACTORY_STALE_AFTER="0"))
        released = not os.path.exists(os.path.join(root, ".git", "dca-factory-worker.lock"))
        check("runner: it takes over a stale claim, runs, and gives the checkout back at the end",
              code == 0 and len(invocations(root)) == 6 and released, f"exit {code}, released {released}")

    # 1q. a session starts knowing where the pipeline stands: AGENTS.md for every tool, a hook for Claude
    with tmpdir() as root:
        build_project(root)
        with open(os.path.join(root, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\nThe project's own line.\n")
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        with open(os.path.join(root, ".claude", "settings.json"), "w", encoding="utf-8") as handle:
            json.dump({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}, handle)
        run_runner(runner, root, "install", "--tool", "claude", "--from", source)
        run_runner(runner, root, "install", "--tool", "claude", "--from", source)
        agents = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
        settings = json.load(open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8"))
        commands = [h["command"] for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]
        check("priming: AGENTS.md carries the pipeline's section once, and keeps the project's own lines",
              agents.count("<!-- dca-factory: start -->") == 1 and "The project's own line." in agents
              and "story-gate.py --status --brief" in agents and "factory.sh status" not in agents, agents[-300:])
        check("priming: Claude's SessionStart hook is added once, beside the project's own hooks",
              sum(1 for c in commands if c.endswith(".agents/factory/story-gate.py --status --brief --session-start")) == 1
              and "echo mine" in commands and not any("factory.sh" in c for c in commands), commands)
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "status", "--brief")
        check("priming: `factory.sh status --brief` prints two lines, ending in what comes next",
              code == 0 and len([l for l in output.splitlines() if l.startswith("factory: ")]) == 2
              and "next:" in output, output.strip().splitlines()[-2:])
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "status", "--brief",
                                  "--session-start")
        check("priming: with --session-start it adds what the session should do with them",
              code == 0 and "At the person's first message" in output and "/factory-backlog" in output,
              output.strip().splitlines()[-1:])

    # 1f. the snapshot sees files in a directory this run added
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
                       cwd=root, capture_output=True)
        os.makedirs(os.path.join(root, "src", "brand-new"))
        with open(os.path.join(root, "src", "brand-new", "Added.java"), "w", encoding="utf-8") as handle:
            handle.write("class Added {}\n")
        os.remove(os.path.join(root, "README.md"))
        run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in", "--from", "judge",
                   env={"FACTORY_TOOL_CMD": 'mkdir -p tasks/STORY-1; printf "## Verdict\\nverdict: pass\\n" '
                                            '> tasks/STORY-1/judge.md'})
        snap = read_snapshot(os.path.join(root, "tasks", "STORY-1", ".verify", "tree-before-judge.txt"))
        check("snapshot: a file inside a directory this run added is hashed, not skipped",
              "src/brand-new/Added.java" in snap,
              f"{len(snap)} entries: {sorted(snap)[:4]}…")
        check("snapshot: a tracked file that is gone is recorded as deleted, not left out",
              snap.get("README.md") == "deleted", f"{len(snap)} entries: {sorted(snap.items())[:4]}…")

    # 1g. no sha256 command on the machine: the snapshot says so instead of recording empty
    # digests, because empty digests compare equal and would read as "this stage changed nothing".
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        code, output = run_runner(
            runner, root, "run", "--story", "STORY-1", "--tool", "stand-in", "--from", "judge",
            env={"FACTORY_SHA256": "none",
                 "FACTORY_TOOL_CMD": 'mkdir -p tasks/STORY-1; printf "## Verdict\\nverdict: pass\\n" '
                                     '> tasks/STORY-1/judge.md'})
        tree = os.path.join(root, "tasks", "STORY-1", ".verify", "tree-before-judge.txt")
        first = open(tree, encoding="utf-8").readline().strip() if os.path.isfile(tree) else ""
        check("snapshot: without a sha256 command the snapshot says so, and the run says it too",
              first.startswith("# no-sha256-command") and "no sha256 command found" in output,
              f"first line {first!r}")
        check("snapshot: the observer reads a names-only snapshot as absent, not as unchanged",
              observe_snapshot(tree) is None,
              "a placeholder digest must never compare equal to a real one")

    # 1h. an install step that cannot write must abort, not report success. A regular file where
    # `.agents/factory` has to be a directory is the cheapest way to make one `mkdir` fail.
    with tmpdir() as root:
        build_project(root)
        shutil.rmtree(os.path.join(root, ".agents"))
        with open(os.path.join(root, ".agents"), "w", encoding="utf-8") as handle:
            handle.write("not a directory\n")
        code, output = run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        check("install: a write that fails aborts the install instead of reporting success",
              code != 0 and "install aborted" in output
              and not os.path.isfile(os.path.join(root, ".agents", "factory", "story-gate.py")),
              f"exit {code}: {output.strip().splitlines()[-1] if output.strip() else ''!r}")

    # 1i. the architecture test is found where source layouts actually put it — several directories
    # down. A `**` glob without `shopt -s globstar` matches one level and reported none.
    with tmpdir() as root:
        build_project(root, extra_sources=(
            ("src/test-architecture/java/com/example/ArchitectureTest.java",
             "class ArchitectureTest {}\n"),))
        code, output = run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        check("install: an architecture test nested in a source set is found",
              "architecture governance found" in output,
              [l for l in output.splitlines() if "governance" in l])

    # 1j. the install stamps where the gate came from, and a later run says when the project is
    # behind the pipeline. The gate itself cannot tell: a copied script has nothing to compare to.
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        stamp = os.path.join(root, ".agents", "factory", "gate.installed")
        stamped = open(stamp, encoding="utf-8").read() if os.path.isfile(stamp) else ""
        check("install: the pipeline's identity and contract are recorded in the project",
              "plugin: dca-factory" in stamped and "version: " in stamped and "contract: " in stamped,
              stamped.strip().replace("\n", " | "))
        check("install: the record carries nothing machine-local, so it can be committed",
              root not in stamped and "source:" not in stamped and "installed:" not in stamped
              and os.sep + "Users" not in stamped,
              "a path or a timestamp would be wrong in every other checkout")
        # a newer pipeline beside the project: the record says this version, the plugin copy says otherwise
        plugin = os.path.join(root, "newer-plugin", "factory-run", "scripts")
        os.makedirs(plugin)
        body = open(os.path.join(os.path.dirname(runner), "story-gate.py"), encoding="utf-8").read()
        with open(os.path.join(plugin, "story-gate.py"), "w", encoding="utf-8") as handle:
            handle.write(body.replace('VERSION = "', 'VERSION = "9.9.9-', 1))
        env = {"FACTORY_PLUGIN_DIR": shell_path(os.path.join(root, "newer-plugin"))}
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude",
                                  "--dry-run", env=env)
        check("install: a run says when the project is behind the pipeline beside it",
              "brings the project up to date" in output,
              [l for l in output.splitlines() if "installed from pipeline" in l])
        # and a differing *contract* is the louder message, because it is a compatibility question
        with open(os.path.join(plugin, "story-gate.py"), "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^CONTRACT = \d+", "CONTRACT = 7", body, count=1, flags=re.M))
        contract = re.search(r"^CONTRACT = (\d+)", body, re.M).group(1)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude",
                                  "--dry-run", env=env)
        check("install: a differing file contract is reported as a compatibility question",
              f"installed against file contract {contract}" in output and "implements 7" in output
              and "stack profile" in output,      # the message wraps, so match per line, not across
              [l for l in output.splitlines() if "contract" in l])

    # 2. the artefact name the runner waits for is the file contract's, not the stage's name
    with tmpdir() as root:
        build_project(root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude",
                                  "--from", "test", "--dry-run")
        check("runner: the test stage's artefact is tests.md, not test.md",
              "tests.md" in output or "would run" in output,
              "the dry run should name the stage assignment")

    # 3. the judge's verdict decides what comes next
    for verdict, expect in (("pass", "pass"), ("changes-requested", "changes-requested"),
                            ("story-conflict", "story-conflict")):
        with tmpdir() as root:
            os.makedirs(os.path.join(root, "tasks", "STORY-1"))
            with open(os.path.join(root, "tasks", "STORY-1", "judge.md"), "w", encoding="utf-8") as handle:
                handle.write(f"# Judge\n\n## Verdict\nverdict: {verdict}\n")
            code, output = run_runner(
                runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                env={"FACTORY_VERIFY_VERDICT": "1"})
            # the dry run does not reach the judge, so read the parser directly
            parsed = subprocess.run(
                [BASH, "-c",
                 f'TASKS=tasks; sed -n "/^verdict_of/,/^}}/p" "{shell_path(runner)}" > fn.sh; '
                 f'. ./fn.sh; verdict_of STORY-1'],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
            check(f"runner: reads the verdict '{verdict}' from the file", parsed == expect,
                  f"parsed {parsed!r}")

    # 4. the round counter is a file, and it counts up
    with tmpdir() as root:
        os.makedirs(os.path.join(root, "tasks", "STORY-1"))
        counted = subprocess.run(
            [BASH, "-c",
             f'TASKS=tasks; sed -n "/^bump_rounds/,/^}}/p" "{shell_path(runner)}" > fn.sh; '
             f'. ./fn.sh; bump_rounds STORY-1; bump_rounds STORY-1'],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
        check("runner: the round counter is a file and counts up", counted == ["1", "2"],
              f"got {counted}")

    # 1s. installing from a plugin cache, re-installing copies, and what an install leaves for git
    def cache_fixture(home, with_core=True):
        """A Claude plugin cache: `<plugin>/<version>/skills`, two versions of the pipeline and of a neighbour."""
        cache = os.path.join(home, ".claude", "plugins", "cache", "m")
        pipeline = os.path.normpath(os.path.join(os.path.dirname(runner), "..", ".."))
        for plugin, version in (("dca-factory", "0.1.0"), ("dca-factory", "0.2.0"), ("dca-core", "0.1.0"),
                                ("dca-core", "0.2.0")):
            if plugin == "dca-core" and not with_core:
                continue
            folder = os.path.join(cache, plugin, version)
            os.makedirs(os.path.join(folder, ".claude-plugin"))
            write_file(folder, ".claude-plugin/plugin.json", json.dumps({"name": plugin, "version": version}))
            if plugin == "dca-factory" and version == "0.2.0":
                shutil.copytree(pipeline, os.path.join(folder, "skills"), symlinks=True)
            else:
                name = "ddd-modelling" if plugin == "dca-core" else "stage-plan"
                write_file(folder, f"skills/{name}/SKILL.md",
                           f"---\nname: {name}\ndescription: {plugin} {version}\n---\n")
        return os.path.join(cache, "dca-factory", "0.2.0", "skills")
    if SYMLINKS:
        with tmpdir() as root, tmpdir() as home:
            build_project(root, profile=PROFILE + "carrier.build: ddd-modelling\n")
            cached = cache_fixture(home)
            run_runner(runner, root, "install", "--tool", "codex", "--from", shell_path(cached), env={"HOME": home})
            skills = os.path.join(root, ".codex", "skills")
            targets = {e: os.path.realpath(os.path.join(skills, e)) for e in os.listdir(skills)} \
                if os.path.isdir(skills) else {}
            check("install: from a plugin cache the neighbours' newest versions are linked, never an older "
                  "version of the pipeline itself",
                  targets.get("ddd-modelling", "").endswith(os.path.join("dca-core", "0.2.0", "skills", "ddd-modelling"))
                  and not any(os.sep + "0.1.0" + os.sep in t for t in targets.values()),
                  {k: v[-40:] for k, v in targets.items() if "0.1.0" in v or k == "ddd-modelling"})
    with tmpdir() as root, tmpdir() as home:
        build_project(root, profile=PROFILE + "carrier.build: ddd-modelling\n")
        cached = cache_fixture(home)
        run_runner(runner, root, "install", "--tool", "claude", "--from", shell_path(cached), "--copy", env={"HOME": home})
        shutil.rmtree(os.path.join(home, ".claude", "plugins", "cache", "m", "dca-core"))
        code, output = run_runner(runner, root, "install", "--tool", "claude", "--from", shell_path(cached), "--copy",
                                  env={"HOME": home})
        carrier_copy = os.path.join(root, ".claude", "skills", "ddd-modelling", "SKILL.md")
        manifest = os.path.join(root, ".claude", "skills", ".dca-factory-skills")
        check("copies: a copied carrier survives a re-install, also when no neighbour has it any more",
              code == 0 and os.path.isfile(carrier_copy)
              and "ddd-modelling" in open(manifest, encoding="utf-8").read().split(), output.strip().splitlines()[-4:])
    with tmpdir() as root:
        build_project(root)
        shells = [b for b in ("/bin/bash",) if os.path.isfile(b)] or [BASH]
        completed = subprocess.run([shells[0], runner, "install", "--tool", "none"], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        check("install: `--tool none` writes gate, runner and hook — also under the system bash",
              completed.returncode == 0 and os.path.isfile(os.path.join(root, ".agents", "factory", "story-gate.py")),
              f"{shells[0]}: exit {completed.returncode}; {(completed.stderr or completed.stdout).strip()[-200:]}")
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "core.hooksPath", ".husky"], cwd=root, capture_output=True)
        with open(os.path.join(root, ".gitattributes"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("*.png binary")                          # no newline at the end
        code, output = run_runner(runner, root, "install", "--tool", "claude")
        hooks = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=root, capture_output=True,
                               text=True).stdout.strip()
        attributes = open(os.path.join(root, ".gitattributes"), encoding="utf-8").read().splitlines()
        check("install: another hook manager's `core.hooksPath` is kept, and the install says how to chain",
              hooks == ".husky" and "left as it is" in output, f"hooksPath {hooks!r}")
        check("install: `.gitattributes` without a final newline keeps its last line whole",
              attributes[:1] == ["*.png binary"] and any(l.startswith("tasks/**") for l in attributes), attributes)
        for command in (["add", "-A"], ["reset", "-q", "--", ".claude"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        staged = subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"), "--change",
                                 "--staged", "--checks", "compile"], cwd=root, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        check("hook: right after a link install the commit check does not refuse the tool folders it left untracked",
              "gate:fail snapshot" not in staged.stdout and os.path.exists(os.path.join(root, ".claude", "skills")),
              [l for l in staged.stdout.splitlines() if "snapshot" in l][:2])
    with tmpdir() as root:
        env = backlog_fixture(root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", "--max-stages", "x",
                                  env=env)
        check("runner: `run` refuses a --max-stages that is not a number, before any stage",
              code == 2 and invocations(root) == [], f"exit {code}")
    if os.name != "nt":
        with tmpdir() as root:
            env = backlog_fixture(root)
            subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
            lock = os.path.join(root, ".git", "dca-factory-worker.lock")
            process = subprocess.Popen([BASH, runner, "run", "--story", "STORY-2", "--tool", "stand-in"], cwd=root,
                                       env=dict(os.environ, FACTORY_TOOL_CMD="sleep 3"),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            time.sleep(1.2)
            process.terminate()
            time.sleep(0.8)
            held_while_running = os.path.exists(lock)
            process.communicate(timeout=30)
            check("runner: a TERM while a stage runs gives the checkout back only after that stage has ended",
                  held_while_running and not os.path.exists(lock) and process.returncode == 143,
                  f"held while running {held_while_running}, released {not os.path.exists(lock)}, "
                  f"exit {process.returncode}")

    # 5. install leaves a live link, not a copy — and the whole set where it can
    source = shell_path(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")))
    with tmpdir() as root:
        build_project(root)
        code, output = run_runner(runner, root, "install", "--tool", "claude", "--from", source)
        target = os.path.join(root, ".claude", "skills")
        if SYMLINKS:
            check("install: the pipeline's skills are one live link for Claude Code",
                  os.path.islink(target) and os.path.realpath(target) == os.path.realpath(source),
                  f"{target} → {os.path.realpath(target) if os.path.exists(target) else 'missing'}")
        else:
            # No symlinks for this account: the install copies and says so, rather than failing
            # on a `ln -s` that this shell cannot honour.
            check("install: without symlinks the skills are copied, and the install says why",
                  os.path.isdir(os.path.join(target, "factory-run")) and not os.path.islink(target)
                  and "copied" in output,
                  [l for l in output.splitlines() if "skills" in l][:2])
        check("install: the gate is copied into the project, where every tool and CI can call it",
              os.path.isfile(os.path.join(root, ".agents", "factory", "story-gate.py")))
        project_runner = os.path.join(root, ".agents", "factory", "factory.sh")
        status_code, status_out = run_runner(project_runner, root, "status") if os.path.isfile(project_runner) \
            else (None, "")
        check("install: the runner is copied beside the gate, and `factory.sh status` works from there",
              status_code == 0 and "== running" in status_out and "== cost" in status_out,
              f"exit {status_code}; {status_out[:120]}")
        usage_code, usage_out = run_runner(project_runner, root, "usage") if os.path.isfile(project_runner) \
            else (None, "")
        check("install: `factory.sh usage` passes on to the gate", usage_code == 0 and "usage:" in usage_out,
              f"exit {usage_code}; {usage_out[:120]}")
        check("install: a stack profile is written when the project has none",
              os.path.isfile(os.path.join(root, ".agents", "factory", "factory.profile.yaml")))
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "codex", "--from", source)
        entries = os.listdir(os.path.join(root, ".codex", "skills"))
        pipeline = {"factory-run", "stage-plan", "stage-test", "stage-build", "stage-tidy",
                    "stage-judge", "stage-document", "factory-backlog", "factory-scope",
                    "factory-decisions", "factory-status", "factory-update"}
        check("install: a tool without plugins also gets the craft the profile may name",
              pipeline.issubset(set(entries)) and len(entries) > len(pipeline),
              f"{len(entries)} skills: {sorted(entries)[:6]}…")
    with tmpdir() as root:
        build_project(root)
        run_runner(runner, root, "install", "--tool", "claude", "--from", source, "--copy")
        target = os.path.join(root, ".claude", "skills", "factory-run")
        check("install --copy: a real copy for a project with no source to point at",
              os.path.isdir(target) and not os.path.islink(target))

    failed = [name for name, ok, _ in results if not ok]
    print(f"\nverify: {len(results) - len(failed)}/{len(results)} runner cases behaved as specified")
    return failed

def main(argv=None):
    parser = argparse.ArgumentParser(description="verify the factory")
    parser.add_argument("--gate", default=DEFAULT_GATE)
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    # Every case runs in a throwaway directory, so a path given relative to the caller's directory
    # would resolve to nothing there — and the whole suite would fail with the gate merely missing.
    args.gate = os.path.abspath(args.gate)
    args.runner = os.path.abspath(args.runner)

    if not os.path.isfile(args.gate):
        print(f"verify: no gate at {args.gate}")
        return 2

    both_green = ["com.example.WidgetPageTest#showsTheThing",
                  "com.example.WidgetUnitTest#showsNothingWhenEmpty"]

    cases = [
        # --- the plan gate ------------------------------------------------
        (Case("plan: a complete story passes", "plan", 0,
              must_pass=("story", "approved", "epic", "context-map", "instruction-size")),
         dict()),
        (Case("plan: an epic missing a field is refused", "plan", 1, must_fail=("epic",)),
         dict(epic=EPIC.replace("domain_contact: the-expert\n", ""))),
        (Case("plan: a draft story is refused", "plan", 1, must_fail=("approved",)),
         dict(story=STORY.replace("status: approved", "status: draft"))),
        (Case("plan: a story without status is skipped, not refused", "plan", 0,
              must_skip=("approved",)),
         dict(story=STORY.replace("status: approved\n", ""))),
        (Case("plan: a context that is not on the map is refused", "plan", 1,
              must_fail=("context-map",)),
         dict(context_map="# Context map\n\n| Context |\n|---|\n| Something else |\n")),
        (Case("plan: no context map at all is skipped and named", "plan", 0,
              must_skip=("context-map",)),
         dict(context_map=None)),
        (Case("plan: three rounds stop the run", "plan", 1, must_fail=("rounds",)),
         dict(rounds=3)),
        (Case("plan: no product scope is a note, not a failure", "plan", 0,
              text=("no product description at backlog/product.md",)),
         dict()),
        (Case("plan: a complete product scope passes", "plan", 0, must_pass=("product",)),
         dict(extra_sources=(("backlog/product.md", PRODUCT),))),
        (Case("plan: a product scope with an empty heading is refused, comments do not count", "plan", 1,
              must_fail=("product",), text=("empty `## Look and feel`",)),
         dict(extra_sources=(("backlog/product.md", PRODUCT.replace(
             "Plain, readable, the project's own stylesheet.", "<!-- style direction -->")),))),
        (Case("plan: a product scope missing a heading is refused", "plan", 1,
              must_fail=("product",), text=("missing `## Qualities`",)),
         dict(extra_sources=(("backlog/product.md", PRODUCT.replace("## Qualities", "## Quality")),))),
        (Case("plan: a `product:` that names no file is refused", "plan", 1, must_fail=("product",)),
         dict(profile=PROFILE + "product: docs/product.md\n")),
        # --- a model per stage, bound to a tool -------------------------------
        (Case("plan: model keys bound to a tool pass", "plan", 0, must_pass=("models",)),
         dict(profile=PROFILE + "model.claude.tidy: model-a\nmodel.claude: model-b\nmodel.codex.document: model-c\n")),
        (Case("plan: an unqualified model key is refused, naming the tool-bound form", "plan", 1,
              must_fail=("models",), text=("`model.tidy` names no tool", "model.<tool>.<stage>")),
         dict(profile=PROFILE + "model.tidy: model-a\n")),
        (Case("plan: a bare `model:` is refused too", "plan", 1, must_fail=("models",), text=("`model` names no tool",)),
         dict(profile=PROFILE + "model: model-a\n")),
        (Case("plan: a misspelt stage in a model key is refused", "plan", 1, must_fail=("models",),
              text=("no stage `tdy`",)),
         dict(profile=PROFILE + "model.claude.tdy: model-a\n")),
        (Case("plan: a misspelt tool in a model key is refused", "plan", 1, must_fail=("models",),
              text=("no tool `clade`",)),
         dict(profile=PROFILE + "model.clade.tidy: model-a\n")),
        # --- the scenario form of acceptance criteria -----------------------
        (Case("plan: keyed scenarios under rules pass, beside an out-of-scope section", "plan", 0,
              must_pass=("story",), text=("with 2 criterion(s)",)),
         dict(story=STORY_SCENARIOS)),
        (Case("test: a scenario's key is what the test stage binds", "test", 0,
              must_pass=("tests-mapped", "tests-red")),
         dict(story=STORY_SCENARIOS)),
        (Case("plan: a rule without a scenario is refused", "plan", 1, must_fail=("gate",),
              text=("has no scenario",)),
         dict(story=STORY_SCENARIOS.replace("### Rule: An empty record is not an error\n",
                                             "### Rule: An empty record is not an error\n\n### Rule: Nothing is lost\n"))),
        (Case("plan: a scenario with two triggers is refused", "plan", 1, must_fail=("gate",),
              text=("has 2 triggers",)),
         dict(story=STORY_SCENARIOS.replace("- When the reader opens the list\n- Then the list shows the thing",
                                             "- When the reader opens the list\n- And sorts it\n- Then the list shows the thing"))),
        (Case("plan: a scenario without an outcome is refused", "plan", 1, must_fail=("gate",),
              text=("has no `Then`",)),
         dict(story=STORY_SCENARIOS.replace("- Then the list shows the thing\n", ""))),
        (Case("plan: an unknown step is refused", "plan", 1, must_fail=("gate",), text=("is not a step",)),
         dict(story=STORY_SCENARIOS.replace("- Then the list is empty", "- Expect the list is empty"))),
        (Case("plan: a key used twice is refused", "plan", 1, must_fail=("gate",), text=("appears twice",)),
         dict(story=STORY_SCENARIOS.replace("#### shows-nothing-when-empty", "#### shows-the-thing"))),
        # --- the test gate ------------------------------------------------
        (Case("test: every criterion mapped and red passes", "test", 0,
              must_pass=("tests-mapped", "tests-exist", "compiles", "tests-red")),
         dict()),
        (Case("test: an unmapped criterion is refused", "test", 1, must_fail=("tests-mapped",)),
         dict(tests="\n".join(TESTS.splitlines()[:5]) + "\n")),
        (Case("test: a selector with no source file is refused", "test", 1,
              must_fail=("tests-exist",)),
         dict(tests=TESTS.replace("WidgetUnitTest", "MissingTest"))),
        (Case("test: a test that is already green is refused", "test", 1, must_fail=("tests-red",)),
         dict(green=both_green)),
        (Case("test: a source set no command covers is refused", "test", 1,
              must_fail=("tests-red",), text=("no declared test command covers",)),
         dict(tests=TESTS.replace("com.example.WidgetPageTest#showsTheThing",
                                  "com.example.OtherTest#showsTheThing"),
              extra_sources=(("src/other/java/com/example/OtherTest.java",
                              "class OtherTest { void showsTheThing() {} }\n"),))),
        (Case("test: a mandatory epic field left blank is refused", "plan", 1, must_fail=("epic",),
              text=("missing domain_contact",)),
         dict(epic=EPIC.replace("domain_contact: the-expert", "domain_contact:"))),
        (Case("test: a runner that cannot start is no evidence", "test", 1,
              must_fail=("tests-red",), text=("no test report from this run shows it ran",)),
         dict(profile=PROFILE.replace("test: sh runner.sh src/test/java",
                                      "test: sh no-such-runner.sh src/test/java\ncovers.test: **"))),
        (Case("test: a runner that reports no test but names the selector is no evidence", "test", 1,
              must_fail=("tests-red",), text=("no test report from this run shows it ran",)),
         # The reviewer's case: it exists, it exits 1, and it prints the selector back — so its
         # output differs per selector while it executes nothing. Only a report settles it.
         dict(profile=PROFILE.replace(
             "test: sh runner.sh src/test/java",
             "test: sh -c 'echo \"no tests found for given includes: $2\"; exit 1' --"
             "\ncovers.test: **"))),
        (Case("test: a crashed runner that exits like a failing test is no evidence", "test", 1,
              must_fail=("tests-red",), text=("no test report from this run shows it ran",)),
         dict(profile=PROFILE.replace("test: sh runner.sh src/test/java",
                                      "test: sh -c 'exit 1' --\ncovers.test: **"))),
        (Case("test: with testEvidence: exit-code the weaker check is named, not hidden", "test", 0,
              must_skip=("tests-red",), text=("rests on the exit code",)),
         dict(profile=PROFILE.replace(
             "test: sh runner.sh src/test/java",
             "test: sh runner-noreport.sh src/test/java\ncovers.test: **\ntestEvidence: exit-code"),
              extra_sources=(("runner-noreport.sh",
                              "#!/bin/sh\necho \"ran $3\"\nexit 1\n"),))),
        (Case("test: a command whose declared scope is everything covers every test", "test", 0,
              must_pass=("tests-red",)),
         dict(profile="compile: true\ntest: sh runner.sh .\ncovers.test: **\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n')),
        (Case("test: a pathless task is not assumed to run another source set", "test", 1,
              must_fail=("tests-red",), text=("no declared test command covers",)),
         # The build-tool shape: `<tool> test` carries no path at all. A test in another source set
         # must not be attributed to it — that task does not run those tests, and calling the
         # criterion covered would certify something nothing executes.
         dict(tests=TESTS.replace("com.example.WidgetPageTest#showsTheThing",
                                  "com.example.OtherTest#showsTheThing"),
              extra_sources=(("src/test-integration/java/com/example/OtherTest.java",
                              "class OtherTest { void showsTheThing() {} }\n"),),
              profile="compile: true\ntest: ./gradlew-stub test\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n')),
        (Case("test: a pathless task still covers its own source set", "test", 0,
              must_pass=("tests-red",)),
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: ./gradlew-stub test\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n')),
        (Case("test: a project file names the directory it covers", "test", 0,
              must_pass=("tests-red",)),
         dict(profile="compile: true\ntest: sh runner.sh src/test/java/com/example/WidgetUnitTest.java\n"
                      "test.pages: sh runner.sh src/test-pages/java\nfilterFlag: --select\n"
                      'filterFormat: "{class}#{method}"\narchitecture: true\n')),
        (Case("test: any stack works when it says where its report is", "test", 0,
              must_pass=("tests-red",)),
         # A runner of no particular ecosystem: it writes JUnit XML — what pytest, jest, gotestsum,
         # nextest, PHPUnit and RSpec all can emit — to a path of its own, declared in the profile.
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: sh other-stack.sh\ncovers.test: **\n"
                      "testReport: reports/junit-*.xml\nfilterFlag: -k\n"
                      'filterFormat: "{class}#{method}"\narchitecture: true\n',
              extra_sources=(("other-stack.sh",
                              '#!/bin/sh\n'
                              '# -k <Class>#<method>, JUnit XML wherever this stack puts it\n'
                              'selector=$2\n'
                              'cls=$(echo "$selector" | sed "s/#.*//")\n'
                              'method=$(echo "$selector" | sed "s/.*#//")\n'
                              'mkdir -p reports\n'
                              'printf \'<testsuite><testcase classname="%s" name="%s">\''
                              '\'<failure>not yet</failure></testcase></testsuite>\\n\' '
                              '"$cls" "$method" > reports/junit-run.xml\n'
                              'echo "1 failed"\nexit 1\n'),))),
        (Case("test: a report from before the run is not this run's evidence", "test", 1,
              must_fail=("tests-red",), text=("no test report from this run shows it ran",)),
         # A failure report left by an earlier run, and a runner that finds nothing now: the old
         # file must not stand in for a test that was never executed.
         dict(profile=PROFILE.replace(
                  "test: sh runner.sh src/test/java",
                  "test: sh -c 'echo \"No tests found\"; exit 1' --\ncovers.test: **"),
              extra_sources=(
                  ("build/test-results/stale/TEST-WidgetUnitTest.xml",
                   '<testsuite><testcase classname="com.example.WidgetUnitTest" '
                   'name="showsNothingWhenEmpty"><failure>from yesterday</failure>'
                   "</testcase></testsuite>\n"),
                  ("build/test-results/stale/TEST-WidgetPageTest.xml",
                   '<testsuite><testcase classname="com.example.WidgetPageTest" '
                   'name="showsTheThing"><failure>from yesterday</failure>'
                   "</testcase></testsuite>\n"),
              ))),
        (Case("test: another method's result does not settle this one", "test", 1,
              must_fail=("tests-red",), text=("case(s) for that class",)),
         # The report holds two cases for the class and neither is named like the mapped method —
         # attributing one of them would let a sibling decide this criterion.
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: sh sibling-runner.sh\ncovers.test: **\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n',
              extra_sources=(("sibling-runner.sh",
                              '#!/bin/sh\nmkdir -p build/test-results/run\n'
                              'printf \'<testsuite>\''
                              '\'<testcase classname="com.example.WidgetUnitTest" name="a nice title">\''
                              '\'<failure>no</failure></testcase>\''
                              '\'<testcase classname="com.example.WidgetUnitTest" name="another title"/>\''
                              '\'</testsuite>\\n\' > build/test-results/run/TEST-WidgetUnitTest.xml\n'
                              'echo "2 tests ran"\nexit 1\n'),))),
        (Case("test: a single case in the class is not the mapped test either", "test", 1,
              must_fail=("tests-red",), text=("1 case(s) for that class", "otherMethod")),
         # The reviewer's case: the report holds exactly one case, and it is a *sibling*. A filtered
         # run is not a promise that the filter was honoured, so one case proves nothing by itself.
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: sh one-sibling-runner.sh\ncovers.test: **\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n',
              extra_sources=(("one-sibling-runner.sh",
                              '#!/bin/sh\nmkdir -p build/test-results/run\n'
                              'printf \'<testsuite><testcase classname="com.example.WidgetUnitTest" \''
                              '\'name="otherMethod"><failure>no</failure></testcase></testsuite>\\n\' '
                              '> build/test-results/run/TEST-WidgetUnitTest.xml\n'
                              'echo "1 test ran"\nexit 1\n'),))),
        (Case("test: a display name declared in the code settles it", "test", 0,
              must_pass=("tests-red",), text=("display name declared in the code",)),
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: sh titled-runner.sh\ncovers.test: **\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n',
              extra_sources=(
                  ("src/test/java/com/example/WidgetUnitTest.java",
                   "class WidgetUnitTest {\n"
                   '  @DisplayName("shows an invitation when nothing is recorded")\n'
                   "  void showsNothingWhenEmpty() {}\n"
                   '  @DisplayName("another title")\n'
                   "  void somethingElse() {}\n}\n"),
                  ("titled-runner.sh",
                   '#!/bin/sh\nmkdir -p build/test-results/run\n'
                   'printf \'<testsuite>\''
                   '\'<testcase classname="com.example.WidgetUnitTest" \''
                   '\'name="shows an invitation when nothing is recorded">\''
                   '\'<failure>not yet</failure></testcase>\''
                   '\'<testcase classname="com.example.WidgetUnitTest" name="another title"/>\''
                   '\'</testsuite>\\n\' > build/test-results/run/TEST-WidgetUnitTest.xml\n'
                   'echo "2 tests ran"\nexit 1\n'),
              ))),
        # --- the version contract -----------------------------------------
        # Two numbers, two jobs: the *contract* says whether this gate can read the project's
        # files at all, so a mismatch is a refusal. The script's *version* is provenance and an
        # update hint, which only the installer can see — the runner checks that, not the gate.
        (Case("contract: a profile written for a newer gate is refused", "plan", 1,
              must_fail=("contract",), text=("re-run `factory.sh install`",)),
         dict(profile="contract: 99\n" + PROFILE)),
        (Case("contract: a profile written for an older gate is still read", "plan", 0,
              text=("worth bringing up to date",)),
         dict(profile="contract: 0\n" + PROFILE)),
        (Case("contract: a profile that declares none is not treated as a failing check", "plan", 0,
              text=("declares no `contract:`",)),
         dict()),
        (Case("contract: a contract that is not a number is refused", "plan", 1,
              must_fail=("contract",)),
         dict(profile="contract: latest\n" + PROFILE)),

        # --- the shape the selector depends on ------------------------------
        # The documented limit, as a case: a selector resolves through a source file *named after
        # the class*. Stated in prose it is a claim; here it is the behaviour, so the day the
        # profile learns to declare another shape, this case is what has to change with it.
        (Case("selector: a class whose file is not named after it is not found", "test", 1,
              must_fail=("tests-exist",), text=("no source file for",)),
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.Widgets#showsNothingWhenEmpty |\n")),

        # --- decision records ----------------------------------------------
        # The question a stage may not answer is a file of its own, so an answer has a place to
        # land and a second session finds it. The gate reads the state off the file: open blocks,
        # a draft is still open, an answer is applied by the stage that asked and stamped here.
        (Case("decisions: a needs-human section without a record has asked nobody", "test", 1,
              must_fail=("decisions",), text=("names no `decision: <id>`",)),
         with_decisions(plan=PLAN_ASKING.replace("decision: STORY-1-01\n", ""))),
        (Case("decisions: a needs-human section naming a record that does not exist is refused", "test", 1,
              must_fail=("decisions",), text=("does not exist or names another story",)),
         with_decisions(plan=PLAN_ASKING)),
        (Case("decisions: an open record blocks the story and says where to answer", "test", 1,
              must_fail=("decisions",),
              text=("STORY-1-01 is open", ".agents/factory/decisions/STORY-1-01.md", "`by:` and `at:`")),
         with_decisions(("STORY-1-01", DECISION), plan=PLAN_ASKING)),
        (Case("decisions: an answer without a name and a time is a draft, and a draft unblocks nothing",
              "test", 1, must_fail=("decisions",), text=("not confirmed", "`by:`")),
         with_decisions(("STORY-1-01", DECISION + "\n## Answer\nanswer: b\n"), plan=PLAN_ASKING)),
        (Case("decisions: an answered record whose stage still asks says which stage to re-run", "test", 1,
              must_fail=("decisions",), text=("re-run that stage", "--from plan")),
         with_decisions(("STORY-1-01", DECISION + ANSWER), plan=PLAN_ASKING)),
        (Case("decisions: a stage that ran again without citing the answer is refused", "test", 1,
              must_fail=("decisions",), text=("does not cite STORY-1-01",)),
         with_decisions(("STORY-1-01", DECISION + ANSWER),
                        plan=PLAN_APPLIED.replace("STORY-1-01", "the decision"))),
        (Case("decisions: an applied answer passes and is stamped in the record", "test", 0,
              must_pass=("decisions",), text=("applied by stage plan", "'b' by the-expert")),
         with_decisions(("STORY-1-01", DECISION + ANSWER), plan=PLAN_APPLIED)),
        (Case("decisions: a record whose id is not its file name is refused", "test", 1,
              must_fail=("decisions",), text=("the two must agree",)),
         with_decisions(("STORY-1-02", DECISION), plan=PLAN_APPLIED)),
        (Case("decisions: a record for another story is not this story's", "test", 0,
              text=("no decision record for this story",)),
         with_decisions(("STORY-9-01", DECISION.replace("STORY-1", "STORY-9")))),
        (Case("decisions: the check runs on every stage, not only the plan gate", "build", 1,
              must_fail=("decisions",), text=("STORY-1-01 is open",)),
         with_decisions(("STORY-1-01", DECISION), green=both_green, ledger=both_green)),
        (Case("decisions: the plan gate lets an answered plan question through — its stage runs next",
              "plan", 0, text=("the plan stage runs next and applies it",)),
         with_decisions(("STORY-1-01", DECISION + ANSWER), plan=PLAN_ASKING)),
        (Case("decisions: an open plan question still stops the plan gate", "plan", 1,
              must_fail=("decisions",), text=("STORY-1-01 is open",)),
         with_decisions(("STORY-1-01", DECISION), plan=PLAN_ASKING)),
        (Case("document: a row saying nothing was updated names no file, and says how that was checked",
              "document", 0, must_pass=("documented",)),
         dict(document=DOCUMENT.replace("| `README.md` | one sentence about the thing | read `README.md:1` |",
                                        "| — | none | `docs/context-map.md:3` still describes the context |"))),
        (Case("document: a nothing-row without `Verified by` is still a claim", "document", 1,
              must_fail=("documented",), text=("the row saying nothing was updated",)),
         dict(document=DOCUMENT.replace("| `README.md` | one sentence about the thing | read `README.md:1` |",
                                        "| — | none | |"))),
        (Case("build: a required suite that ran nothing fails the build gate, though the story's tests are green",
              "build", 1, must_fail=("suite",), text=("no report written by this run shows an executed test",)),
         dict(green=both_green, ledger=both_green, profile=PROFILE + "required: test\n")),
        (Case("build: a required test command the profile does not declare fails the build gate", "build", 1,
              must_fail=("suite",), text=("no `test.integration:` command",)),
         dict(green=both_green, ledger=both_green, profile=PROFILE + "required: test.integration\n")),
        (Case("plan: an epic field written as `\"\"` is empty, not filled", "plan", 1, must_fail=("epic",),
              text=("missing intent",)),
         dict(epic=EPIC.replace("intent: Someone cannot see something they need", 'intent: ""'))),
        (Case("build: without a policy the build gate runs only the story's tests, as before", "build", 0,
              must_pass=("tests-green",)),
         dict(green=both_green, ledger=both_green)),
        (Case("document: an empty `## needs-human` left from the template stops nothing", "document", 0,
              must_pass=("documented",)),
         dict(document=DOCUMENT + "\n## needs-human\n(none)\n")),
        (Case("document: `## needs-human` with a sentence-cased `None.` stops nothing either", "document", 0,
              must_pass=("documented",)),
         dict(document=DOCUMENT + "\n## needs-human\nNone.\n")),
        (Case("document: `## needs-human` with `- None.` or `_None._` stops nothing either", "document", 0,
              must_pass=("documented",)),
         dict(document=DOCUMENT + "\n## needs-human\n- None.\n_None._\n")),
        (Case("test: a test recorded red before may be green when its expectation changed on a decision",
              "test", 0, must_pass=("tests-red", "decisions"), text=("expectation changed on decision STORY-1-01",)),
         dict(tests=TESTS_ON_DECISION, green=both_green, ledger=both_green,
              **with_decisions(("STORY-1-01", CONFLICT + ANSWER), plan=PLAN_APPLIED))),
        (Case("test: without that decision, green before the build is still refused", "test", 1,
              must_fail=("tests-red",), text=("passes before the build stage",)),
         dict(green=both_green, ledger=both_green)),
        # --- the build gate -----------------------------------------------
        # --- the hand-over names what the stage changed ------------------------
        (Case("build: a hand-over that lists every changed file passes the files check", "build", 0,
              must_pass=("files-listed",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             ("tasks/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\nmodified\tsrc/main/Page.java\n"),
             ("tasks/STORY-1/build.md", "## Changed\n\n## Files\n\n- `src/main/Thing.java` — new\n"
                                        "- `src/main/Page.java` — shows it\n")))),
        (Case("build: a changed file the hand-over does not list is refused, named", "build", 1,
              must_fail=("files-listed",), text=("src/main/Page.java",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             ("tasks/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\nmodified\tsrc/main/Page.java\n"),
             ("tasks/STORY-1/build.md", "## Changed\n| File | Why |\n|---|---|\n| `src/main/Thing.java` | new |\n")))),
        (Case("build: a hand-over without a Files section is refused", "build", 1,
              must_fail=("files-listed",), text=("has no `## Files` section",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             ("tasks/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\n"),
             ("tasks/STORY-1/build.md", "## Criteria\n")))),
        (Case("build: without a changed-files record the files check is skipped and named", "build", 0,
              must_skip=("files-listed",)),
         dict(green=both_green, ledger=both_green)),
        (Case("build: green with the test stage's record passes", "build", 0,
              must_pass=("tests-green", "architecture"),
              text=("via `test.pages:`", "via `test:`")),
         dict(green=both_green, ledger=both_green)),
        (Case("build: green without any record is skipped and named", "build", 0,
              must_skip=("tests-green",), text=("no `.tests-red`",)),
         dict(green=both_green)),
        (Case("build: green but missing from the record is refused", "build", 1,
              must_fail=("tests-green",), text=("never recorded red",)),
         dict(green=both_green, ledger=both_green[:1])),
        (Case("build: a red test is refused", "build", 1, must_fail=("tests-green",)),
         dict(ledger=both_green)),
        # --- the tidy gate ------------------------------------------------
        (Case("tidy: the build gate's checks, run again", "tidy", 0,
              must_pass=("tests-green", "architecture")),
         dict(green=both_green, ledger=both_green)),
        # --- the document gate --------------------------------------------
        (Case("document: a path with its line number resolves", "document", 0,
              must_pass=("documented",)),
         dict(green=both_green, ledger=both_green, document=DOCUMENT)),
        (Case("document: an invented path is refused", "document", 1, must_fail=("documented",)),
         dict(green=both_green, ledger=both_green,
              document=DOCUMENT.replace("`README.md`", "`docs/invented.md`"))),
        (Case("document: a glossary row without a source is refused", "document", 1,
              must_fail=("documented",)),
         dict(green=both_green, ledger=both_green,
              document=DOCUMENT.replace("`docs/context-map.md:3` — the context's own description", ""))),
        (Case("document: a needs-human section stops the run", "document", 1,
              must_fail=("documented",)),
         dict(green=both_green, ledger=both_green,
              document=DOCUMENT + "\n## needs-human\n\nSomeone has to decide.\n")),
    ]

    # --- the second shape, on a real runner ----------------------------------
    # The cases above drive stubs, so they prove the gate's logic and nothing about a runner. These
    # drive pytest: a module-path selector is found, filtered by `{file}`, and read back from the
    # JUnit XML pytest writes — the whole chain for a stack whose tests are functions, not classes.
    if pytest_available():
        function = "tests.test_widgets#test_shows_the_thing"
        in_class = "tests.test_widgets.TestWidgets#test_shows_nothing_when_empty"
        parametrised = "tests.test_widgets#test_in_every_case"
        cases += [
            # a module-level function: the module *is* the file named after the class part, so
            # the first shape finds it; the filter and the report are what is new here
            (Case("pytest: a function in a module is found, selected by file and read back", "test", 0,
                  must_pass=("tests-exist", "tests-red"),
                  text=("via `test:`", "report by name")),
             pytest_project("shows-the-thing", function)),
            (Case("pytest: the same function turns green, and the report says so", "build", 0,
                  must_pass=("tests-green",), text=("report by name",)),
             pytest_project("shows-the-thing", function, green=[function], ledger=[function])),
            (Case("pytest: a method in a class inside the module is found — and not yet selectable",
                  "test", 1, must_pass=("tests-exist",), must_fail=("tests-red",),
                  text=("by the module path", "no test report from this run shows it ran")),
             pytest_project("shows-nothing-when-empty", in_class)),
            (Case("pytest: a function the module does not declare is not found", "test", 1,
                  must_fail=("tests-exist",), text=("has no test_nobody_wrote",)),
             pytest_project("shows-the-thing", "tests.test_widgets#test_nobody_wrote")),
            (Case("pytest: a parametrised test is one test, and one failing case fails it", "build", 1,
                  must_fail=("tests-green",)),
             pytest_project("shows-the-thing", parametrised,
                            green=[parametrised + "-a"], ledger=[parametrised])),
        ]
    else:
        print(f"verify: pytest is not importable by {sys.executable} — the pytest cases were "
              f"skipped, which proves nothing about that stack (pip install pytest)")

    failures = []
    for case, fixture in cases:
        with tmpdir() as root:
            build_project(root, **fixture)
            code, output = run_gate(args.gate, root, case.stage)
            found = checks_by_verdict(output)
            problems = []
            if code != case.expect_exit:
                problems.append(f"exit {code}, expected {case.expect_exit}")
            for check in case.must_pass:
                if check not in found["pass"]:
                    problems.append(f"'{check}' did not pass")
            for check in case.must_fail:
                if check not in found["fail"]:
                    problems.append(f"'{check}' did not fail")
            for check in case.must_skip:
                if check not in found["skip"]:
                    problems.append(f"'{check}' was not skipped")
            for needle in case.text:
                if needle not in output:
                    problems.append(f"the report never says {needle!r}")
            if problems:
                failures.append((case.name, problems, output))
                print(f"  FAIL  {case.name}")
                for problem in problems:
                    print(f"          {problem}")
                if args.verbose:
                    print("        --- gate output ---")
                    for line in output.splitlines():
                        print(f"        {line}")
            else:
                print(f"  ok    {case.name}")

    print(f"\nverify: {len(cases) - len(failures)}/{len(cases)} gate cases behaved as specified")

    # --- the inbox: one listing a second session can act on --------------------
    # Not a stage gate, so not a Case: the listing reads the store alone and orders it so that
    # what waits on a human comes first. Read from files only — a record's state is never stored.
    print()
    inbox_failures = []
    with tmpdir() as root:
        build_project(root, **with_decisions(
            ("STORY-1-01", DECISION),
            ("STORY-1-02", DECISION.replace("STORY-1-01", "STORY-1-02") + "\n## Answer\nanswer: a\n"),
            ("STORY-1-03", DECISION.replace("STORY-1-01", "STORY-1-03") + ANSWER),
            ("STORY-1-04", DECISION.replace("STORY-1-01", "STORY-1-04") + ANSWER
             + "\n## Applied\nat: 2026-09-22T21:30:00Z\nstage: plan\n"),
            ("STORY-9-01", DECISION.replace("STORY-1", "STORY-9"))))
        listing = subprocess.run([sys.executable, args.gate, "--list-decisions"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in listing.stdout.splitlines() if l and not l.startswith("decisions:")]
        states = [l.split()[1] for l in lines]
        expectations = [
            ("inbox: every record is listed, open first, then draft, answered, applied",
             states == ["open", "open", "draft", "answered", "applied"], f"states in order: {states}"),
            ("inbox: an answered record shows its answer and who gave it",
             any("STORY-1-03" in l and "→ b by the-expert" in l for l in lines),
             [l for l in lines if "STORY-1-03" in l]),
            ("inbox: the summary counts what waits on a human",
             "5 record(s), 3 waiting for an answer" in listing.stdout,
             listing.stdout.strip().splitlines()[-1:] if listing.stdout.strip() else "no output"),
        ]
        one_story = subprocess.run([sys.executable, args.gate, "--list-decisions", "--story", "STORY-9"],
                                   cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations.append(("inbox: --story narrows the listing to one story",
                             "STORY-9-01" in one_story.stdout and "STORY-1-01" not in one_story.stdout
                             and "1 record(s), 1 waiting" in one_story.stdout,
                             one_story.stdout.strip().splitlines()[-1:]))
        for name, ok, detail in expectations:
            print(f"  {'ok   ' if ok else 'FAIL '} {name}")
            if not ok:
                print(f"          {detail}")
                inbox_failures.append(name)
    failures += [(name, [], "") for name in inbox_failures]

    # --- the change check: the same checks outside a story, and the commit checks what it commits
    print()
    change_failures = []
    expectations = []
    with tmpdir() as root:
        change_project(root, "compile: true\n")
        code, output = run_change(args.gate, root)
        verdicts = checks_by_verdict(output)
        expectations.append(("change: without `required:` the check is report-only and names what it skipped",
                             code == 0 and "test" in verdicts["skip"] and "report-only" in output,
                             output.strip().splitlines()[-3:]))
    with tmpdir() as root:
        change_project(root, "compile: true\ntest: sh suite.sh\nrequired: compile test architecture\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: a required check the profile does not declare fails",
                             code == 1 and "architecture" in checks_by_verdict(output)["fail"]
                             and "`architecture` is required" in output, output.strip().splitlines()[-3:]))
    with tmpdir() as root:
        change_project(root, "compile: true\ntest: sh suite.sh\nrequired: compile test\n", state="empty")
        code, output = run_change(args.gate, root)
        expectations.append(("change: a required test command that ran no test fails, though it exited 0",
                             code == 1 and "no report written by this run shows an executed test" in output,
                             output.strip().splitlines()[-3:]))
    with tmpdir() as root:
        change_project(root, "compile: true\ntest: sh suite.sh\nrequired: compile test\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: a required suite that ran and passed passes",
                             code == 0 and "ran 1 case(s), none failed" in output, output.strip().splitlines()[-3:]))
        # an end-user suite that needs a running system runs nothing here; it is not required
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("e2eTest: sh runner.sh src/test-pages/java\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: a test command that is not required and ran nothing is named, not failed",
                             code == 0 and "(e2eTest) exited 0, but no report" in output
                             and "e2eTest" not in output.split("gate:pass policy")[1].split("\n")[0],
                             output.strip().splitlines()[-4:]))
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("format: false\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: with a policy, a red optional check is reported and does not decide",
                             code == 0 and "optional (not in `required:`), so it does not decide" in output,
                             output.strip().splitlines()[-4:]))
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("required: compile test e2eTest format\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: `required:` binds each test command by its own key",
                             code == 1 and "(e2eTest) exited 0, but no report" in output
                             and "format" in checks_by_verdict(output)["fail"]
                             and "ran 1 case(s)" in output, output.strip().splitlines()[-4:]))
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("required: compile test\n")
        code, output = run_change(args.gate, root, "--checks", "compile")
        expectations.append(("change: a narrowed scope names a required check it left out, never passes it",
                             code == 0 and "test" in checks_by_verdict(output)["skip"]
                             and "a later scope (CI) has to run it" in output, output.strip().splitlines()[-3:]))
    with tmpdir() as root:
        change_project(root, "compile: true\ntest: sh suite.sh\nrequired: compile test\n", repository=True)
        # staged: broken; working tree: the fix, not staged
        write_file(root, "src/state", "broken\n")
        subprocess.run(["git", "add", "src/state"], cwd=root, capture_output=True)
        write_file(root, "src/state", "fixed\n")
        code, output = run_change(args.gate, root, "--staged")
        expectations.append(("change: a failing staged version with an unstaged fix beside it is refused",
                             code == 1 and "modified, not staged: src/state" in output
                             and "ran 1 case" not in output, output.strip().splitlines()[-4:]))
        code, output = run_change(args.gate, root)
        expectations.append(("change: the same tree checked as a working tree passes — the index is what differs",
                             code == 0, output.strip().splitlines()[-2:]))
        write_file(root, "src/state", "broken\n")
        write_file(root, "src/extra.txt", "not staged\n")
        code, output = run_change(args.gate, root, "--staged")
        expectations.append(("change: an untracked file is drift too — the commit would not contain it",
                             code == 1 and "untracked: src/extra.txt" in output, output.strip().splitlines()[-4:]))
        os.remove(os.path.join(root, "src", "extra.txt"))
        code, output = run_change(args.gate, root, "--staged")
        expectations.append(("change: a staged version that fails is refused, with the working tree matching it",
                             code == 1 and "index tree" in output and "failed" in output,
                             output.strip().splitlines()[-3:]))
        state_before = open(os.path.join(root, "src", "state"), encoding="utf-8").read()
        expectations.append(("change: checking leaves the user's files as they were",
                             state_before == "broken\n", state_before))
    with tmpdir() as root:
        # the hook is the same command; `git commit -a` hands it a temporary index
        change_project(root, "compile: true\ntest: sh suite.sh\nrequired: compile test\n", repository=True)
        os.makedirs(os.path.join(root, ".githooks"), exist_ok=True)
        shutil.copy(os.path.join(os.path.dirname(args.gate), "..", "templates", "githooks", "pre-commit"),
                    os.path.join(root, ".githooks", "pre-commit"))
        os.chmod(os.path.join(root, ".githooks", "pre-commit"), 0o755)
        shutil.copy(args.gate, os.path.join(root, ".agents", "factory", "story-gate.py"))
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=root, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)      # a project commits both
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "gate",
                        "--no-verify"], cwd=root, capture_output=True)
        environment = dict(os.environ, FACTORY_PYTHON=shell_path(sys.executable))
        commit = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam"]
        write_file(root, "src/state", "broken\n")
        refused = subprocess.run(commit + ["broken"], cwd=root, capture_output=True, text=True, env=environment)
        write_file(root, "src/state", "fixed, and changed\n")
        accepted = subprocess.run(commit + ["fixed"], cwd=root, capture_output=True, text=True, env=environment)
        log = subprocess.run(["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
        expectations.append(("change: the commit hook refuses `git commit -a` of a failing version",
                             refused.returncode != 0 and "commit refused" in refused.stderr
                             and "1 failing case(s)" in refused.stderr and "not staged" not in refused.stderr,
                             (refused.stdout + refused.stderr).strip().splitlines()[-3:]))
        expectations.append(("change: the commit hook lets `git commit -a` of a passing version through",
                             accepted.returncode == 0 and log[:1] == ["fixed"] and "broken" not in log
                             and "ran 1 case(s)" in accepted.stderr,
                             f"log {log}; {(accepted.stdout + accepted.stderr).strip().splitlines()[-3:]}"))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            change_failures.append(name)
    failures += [(name, [], "") for name in change_failures]

    # --- parity: every implementation proves every mandatory scenario, from its own reports -------
    print()
    parity_failures = []
    with tmpdir() as root:
        reports = {
            "complete": ("one/TEST-x.xml", junit(("The reader sees the thing", "passed"),
                                                 ("An empty list shows v1.0 of nothing", "passed"),
                                                 ("The thing shows inside a frame", "skipped"))),
            "trx": ("two/results.trx", trx(("The reader sees the thing", "Passed"),
                                           ("An empty list shows v1.0 of nothing", "Passed"))),
            "skipping": ("three/TEST-x.xml", junit(("The reader sees the thing", "passed"),
                                                   ("An empty list shows v1.0 of nothing", "skipped"))),
            "missing": ("four/TEST-x.xml", junit(("The reader sees the thing", "passed"))),
            "failing": ("five/TEST-x.xml", junit(("The reader sees the thing", "failed"),
                                                 ("An empty list shows v1.0 of nothing", "passed"))),
            "unbound": ("six/TEST-x.xml", junit(("showsTheThing", "passed"))),
        }
        config = "scenarios: contract/scenarios.md\n"
        os.makedirs(os.path.join(root, "contract"))
        write_file(root, "contract/scenarios.md", SCENARIOS)
        for name, (path, body) in reports.items():
            os.makedirs(os.path.join(root, os.path.dirname(path)), exist_ok=True)
            write_file(root, path, body)
            config += f"implementation.{name}: {os.path.dirname(path)}/**/*.{path.rsplit('.', 1)[1]}\n"
        config += "implementation.absent: seven/**/*.xml\n"
        write_file(root, "parity.conf", config)
        completed = subprocess.run([sys.executable, args.gate, "--parity", "parity.conf"], cwd=root,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = completed.stdout + completed.stderr
        verdicts = checks_by_verdict(output)
        expectations = [
            ("parity: an implementation that proves every mandatory scenario passes; a bound one may skip",
             "complete" in verdicts["pass"] and "not proven here" in output and "scenario.thing.embedded" in output,
             [l for l in output.splitlines() if "complete" in l]),
            ("parity: a TRX report binds by its test name, dots and all",
             "trx" in verdicts["pass"], [l for l in output.splitlines() if "trx" in l]),
            ("parity: a skipped mandatory scenario fails, though the suite passed",
             "skipping" in verdicts["fail"] and "scenario.thing.empty skipped" in output,
             [l for l in output.splitlines() if "skipping" in l]),
            ("parity: a mandatory scenario missing from the reports fails",
             "missing" in verdicts["fail"] and "scenario.thing.empty missing" in output,
             [l for l in output.splitlines() if "missing" in l]),
            ("parity: a failing scenario fails its implementation, not the other ones",
             "failing" in verdicts["fail"] and "scenario.thing.shown failed" in output,
             [l for l in output.splitlines() if "failing" in l]),
            ("parity: reports that name no scenario at all mean the binding is gone",
             "unbound" in verdicts["fail"] and "binding" in output, [l for l in output.splitlines() if "unbound" in l]),
            ("parity: an implementation without reports fails and says to run its suite",
             "absent" in verdicts["fail"] and "run its suite first" in output,
             [l for l in output.splitlines() if "absent" in l]),
            ("parity: the verdict names the contract's digest, and one failure fails the whole check",
             completed.returncode == 1 and "sha256" in output, output.strip().splitlines()[-1:]),
        ]
    with tmpdir() as root:
        os.makedirs(os.path.join(root, "one"))
        write_file(root, "scenarios.md", SCENARIOS + "\n## scenario.thing.untitled\n**Title:** Bold is not the line\n")
        write_file(root, "one/TEST-x.xml", junit(("The reader sees the thing", "passed"),
                                                 ("An empty list shows v1.0 of nothing", "passed")))
        write_file(root, "parity.conf", "scenarios: scenarios.md\nimplementation.one: one/**/*.xml\n")
        completed = subprocess.run([sys.executable, args.gate, "--parity", "parity.conf"], cwd=root,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations.append(("parity: a scenario without its `Title:` line fails the contract, not left out",
                             completed.returncode == 1 and "gate:fail contract" in completed.stdout
                             and "scenario.thing.untitled" in completed.stdout, completed.stdout.strip()[-300:]))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            parity_failures.append(name)
    failures += [(name, [], "") for name in parity_failures]

    # --- the red proof is about one version of a test ------------------------------------------------
    print()
    proof_failures, expectations = [], []
    with tmpdir() as root:
        build_project(root)
        run_gate(args.gate, root, "test")
        ledger = open(os.path.join(root, "tasks", "STORY-1", ".tests-red"), encoding="utf-8").read()
        expectations.append(("red-proof: the test gate records each red test with its file's digest",
                             ledger.count("\t") == 2, ledger.strip()))
        os.makedirs(os.path.join(root, "green"), exist_ok=True)
        for selector in both_green:
            with open(os.path.join(root, "green", re.sub(r"[./#]", "", selector)), "w") as handle:
                handle.write("")
        code, output = run_gate(args.gate, root, "build")
        expectations.append(("red-proof: the build gate passes a test that is the version seen failing",
                             "red-proof" in checks_by_verdict(output)["pass"], [l for l in output.splitlines() if "red-proof" in l]))
        page_test = os.path.join(root, "src", "test-pages", "java", "com", "example", "WidgetPageTest.java")
        with open(page_test, "w", encoding="utf-8") as handle:
            handle.write("class WidgetPageTest { void showsTheThing() { /* the assertion went */ } }\n")
        code, output = run_gate(args.gate, root, "build")
        expectations.append(("red-proof: a test changed after it was seen failing fails the build gate",
                             code == 1 and "red-proof" in checks_by_verdict(output)["fail"]
                             and "WidgetPageTest.java" in output, [l for l in output.splitlines() if "red-proof" in l]))
        os.makedirs(os.path.join(root, ".agents", "factory", "decisions"), exist_ok=True)
        with open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"), "w", encoding="utf-8") as handle:
            handle.write(CONFLICT + ANSWER)
        with open(os.path.join(root, "tasks", "STORY-1", "tests.md"), "a", encoding="utf-8") as handle:
            handle.write("\nDecision STORY-1-01 answered b: the expectation of shows-the-thing changed.\n")
        code, output = run_gate(args.gate, root, "build")
        expectations.append(("red-proof: the same change passes on an answered decision of the test stage",
                             "red-proof" in checks_by_verdict(output)["pass"], [l for l in output.splitlines() if "red-proof" in l]))
    with tmpdir() as root:
        build_project(root, green=both_green, ledger=both_green)
        code, output = run_gate(args.gate, root, "build")
        expectations.append(("red-proof: a red record without digests (an older gate) is skipped and named",
                             code == 0 and "red-proof" in checks_by_verdict(output)["skip"],
                             [l for l in output.splitlines() if "red-proof" in l]))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                             ("tasks/STORY-1/.verify/journal.tsv",
                                              "t\tstage-start\tplan\ttool=x\nt\tstage-end\tplan\texit=0\n"
                                              "t\tstage-start\ttest\ttool=x\n")))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: each story shows the stage invocations its journal recorded",
                             "2 stage invocation(s)" in output, [l for l in output.splitlines() if "STORY-1" in l]))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            proof_failures.append(name)
    failures += [(name, [], "") for name in proof_failures]

    # --- the two usage formats the runner reads, in the shape the tools really write ------------------
    with tmpdir() as root:
        claude_out = os.path.join(root, "claude.json")
        with open(claude_out, "w", encoding="utf-8") as handle:
            handle.write('{"type":"result","result":"ok","total_cost_usd":0.023707,"usage":{"input_tokens":10},'
                         '"modelUsage":{"claude-haiku-4-5":{"inputTokens":10,"outputTokens":79,'
                         '"cacheReadInputTokens":14220,"cacheCreationInputTokens":10940,"costUSD":0.023707}}}')
        codex_out = os.path.join(root, "codex.jsonl")
        with open(codex_out, "w", encoding="utf-8") as handle:
            handle.write('{"type":"thread.started","thread_id":"t"}\n{"type":"turn.started"}\n'
                         '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
                         '{"type":"turn.completed","usage":{"input_tokens":12850,"cached_input_tokens":9984,'
                         '"cache_write_input_tokens":0,"output_tokens":5,"reasoning_output_tokens":0}}\n')
        read = lambda *a: subprocess.run([sys.executable, args.gate, "--usage-from", *a], capture_output=True,
                                         text=True, encoding="utf-8").stdout
        c, x, n = read("claude-json", claude_out), read("codex-jsonl", codex_out, "--usage-model", "gpt-x"), \
            read("none", codex_out)
        expectations = [
            ("usage: Claude's JSON result is read per model, with its cost",
             c.startswith("model=claude-haiku-4-5\tinput=10\tcache_read=14220\tcache_write=10940\toutput=79\tcost=0.0237"), c),
            ("usage: Codex's JSONL is read from its turn events, cached input apart",
             x.startswith("model=gpt-x\tinput=2866\tcache_read=9984\tcache_write=0\toutput=5") and "ok" in x, x),
            ("usage: an unknown format reads as unknown", n.startswith("unknown"), n[:40]),
        ]
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- usage inside a session: the tool's own log, read for the window between two marks ------------
    with tmpdir() as root:
        home = os.path.join(root, "claude-home")
        session = "0000-session"
        log_dir = os.path.join(home, "projects", "-some-project")
        os.makedirs(os.path.join(log_dir, session, "subagents"))
        def response(stamp, mid, out, model="claude-x"):
            return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
                "id": mid, "model": model, "usage": {"input_tokens": 1, "cache_read_input_tokens": 100,
                                                     "cache_creation_input_tokens": 10, "output_tokens": out}}})
        with open(os.path.join(log_dir, f"{session}.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                response("2026-09-23T10:00:00.000Z", "m0", 999),                    # before the stage
                # in it: one response written as three blocks, the output growing to its last one — as
                # Claude Code writes it; counting the first block alone would read 3 instead of 50
                response("2026-09-23T10:01:00.000Z", "m1", 3),
                response("2026-09-23T10:01:00.100Z", "m1", 3),
                response("2026-09-23T10:01:00.200Z", "m1", 50),
                response("2026-09-23T10:01:30.000Z", "s1", 0, "<synthetic>"),       # no model call
                response("2026-09-23T10:09:00.000Z", "m9", 999)]) + "\n")          # after it
        with open(os.path.join(log_dir, session, "subagents", "agent-a.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(response("2026-09-23T10:02:00.000Z", "a1", 7) + "\n")
        journal = os.path.join(root, "tasks", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:00:30.000Z\tstage-start\tplan\ttool=claude-session\n")
        environment = dict(os.environ, CLAUDE_CODE_SESSION_ID=session, CLAUDE_CONFIG_DIR=home)
        # the mark runs "now"; the log is from the past, so the window is closed by hand as the mark would
        subprocess.run([sys.executable, args.gate, "--stage-end", "plan", "--story", "S-1"], cwd=root,
                       env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = open(journal, encoding="utf-8").read().splitlines()
        recorded = [l for l in lines if "\tusage\t" in l]
        if recorded:
            fixed = recorded[0].split("\t")
            fixed = [("window=2026-09-23T10:00:30.000Z/2026-09-23T10:05:00.000Z" if f.startswith("window=") else f)
                     for f in fixed]
            with open(journal, "w", encoding="utf-8") as handle:
                handle.write("\n".join(l for l in lines if "\tusage\t" not in l) + "\n" + "\t".join(fixed) + "\n")
        report = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        row = next((l for l in report.splitlines() if l.startswith("S-1/plan")), "")
        codex_home = os.path.join(root, "codex-home")
        rollout = os.path.join(codex_home, "sessions", "2026", "09", "23", "rollout-x.jsonl")
        os.makedirs(os.path.dirname(rollout))
        def totals(stamp, inp, cached, out):
            return json.dumps({"timestamp": stamp, "type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached,
                                      "cache_write_input_tokens": 0, "output_tokens": out}}}})
        with open(rollout, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                json.dumps({"type": "session_meta", "payload": {"cwd": root}}),
                json.dumps({"type": "turn_context", "payload": {"model": "codex-model"}}),
                totals("2026-09-23T10:00:00.000Z", 1000, 800, 10),                 # before the stage
                totals("2026-09-23T10:02:00.000Z", 3000, 2000, 40),
                totals("2026-09-23T10:02:00.000Z", 3000, 2000, 40)]) + "\n")      # repeated: totals, not sums
        whole = subprocess.run([sys.executable, args.gate, "--usage-from", "codex-session", rollout],
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:01:00.000Z\tstage-start\ttest\ttool=codex-session\n"
                         f"2026-09-23T10:03:00.000Z\tusage\ttest\ttool=codex-session\t"
                         f"window=2026-09-23T10:01:00.000Z/2026-09-23T10:03:00.000Z\tlog={rollout}\n")
        report2 = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        test_row = next((l for l in report2.splitlines() if l.startswith("S-1/test")), "")
        # the next stage mark writes what can be read into the journal; `--usage` itself only reads
        subprocess.run([sys.executable, args.gate, "--stage-start", "document", "--story", "S-1"], cwd=root,
                       env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations = [
            ("usage in a session: the mark records the window and the session's id — no path, which would name "
             "the machine and the person in a committed file",
             bool(recorded) and "window=" in recorded[0] and "session=claude:0000-session" in recorded[0]
             and "log=" not in recorded[0] and home not in recorded[0], recorded[:1]),
            ("usage in a session: Claude's log is read for the window, each response once, subagents included, "
             "synthetic entries left out", row.split()[1:7] == ["1", "1", "2", "200", "20", "57"], row),
            ("usage in a session: a session log has no cost, and the report says so rather than 0.00",
             row.split()[-1:] == ["—"], row),
            ("usage in a session: at the next stage mark the numbers are written into the journal and the "
             "machine-local log path leaves it",
             any("output=57" in l and "log=" not in l for l in open(journal, encoding="utf-8").read().splitlines()),
             [l for l in open(journal, encoding="utf-8").read().splitlines() if "usage" in l][:1]),
            ("usage in a session: Codex's running totals are differenced over the window",
             test_row.split()[3:7] == ["800", "1200", "0", "30"], test_row),
            ("usage from a whole old log: a Codex session is read to its last total",
             whole.startswith("model=codex-model\tinput=1000\tcache_read=2000\tcache_write=0\toutput=40"), whole),
        ]
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- status: what runs, what waits, every story, the cost — in one look -------------------------
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", []), extra_sources=(
            ("tasks/STORY-1/plan.md", PLAN_ASKING),
            (".agents/factory/decisions/STORY-1-01.md", DECISION),
            ("tasks/STORY-2/.verify/journal.tsv",
             "2026-09-23T10:00:00Z\tstage-start\tplan\ttool=x\n2026-09-23T10:01:00Z\tstage-end\tplan\texit=0\n"
             "2026-09-23T10:01:00Z\tusage\tplan\ttool=x\tmodel=m\tinput=10\tcache_read=0\tcache_write=0\toutput=90\tcost=0.01\n"
             "2026-09-23T10:02:00Z\tstage-start\ttest\ttool=x\n")))
        out = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True, text=True,
                             encoding="utf-8").stdout
        section = lambda name: out.split(f"== {name}")[1].split("\n== ")[0] if f"== {name}" in out else ""
        expectations = [
            ("status: a stage with a start and no end is shown as running, with when it started",
             "STORY-2  stage test  since 2026-09-23T10:02:00Z" in section("running"), section("running")),
            ("status: an open decision is listed with the story it blocks",
             "STORY-1-01  open  STORY-1/plan" in section("waiting for a human"), section("waiting for a human")),
            ("status: every story's state is there, and the cost per story and in total",
             "STORY-1  waiting" in section("stories")
             and re.search(r"^STORY-2\s+2\s+1\s+100\s+0\.01$", section("cost"), re.M)
             and re.search(r"^total\s+2\s+1\s+100\s+0\.01$", section("cost"), re.M)
             and "1 invocation(s) without a usage report" in section("cost"), section("cost")),
        ]
        out = subprocess.run([sys.executable, args.gate, "--status", "--story", "STORY-2"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8").stdout
        expectations += [
            ("status of one story: its cost per stage, each stage its own row, and the story's total",
             re.search(r"^plan\s+1\s+1\s+10\s+0\s+0\s+90\s+100\s+0\.01\s+m$", section("cost of STORY-2, per stage"), re.M)
             and re.search(r"^test\s+1\s+0\s+0\s+0\s+0\s+0\s+0\s+—$", section("cost of STORY-2, per stage"), re.M)
             and re.search(r"^total\s+2\s+1\s+10\s+0\s+0\s+90\s+100\s+0\.01$",
                           section("cost of STORY-2, per stage"), re.M)
             and "== stories" in out, out.split("== cost")[-1]),
        ]
    with tmpdir() as root:
        # switched off: the gate records the stage and reads no session log
        journal = os.path.join(root, "tasks", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:00:30.000Z\tstage-start\tplan\ttool=claude-session\n")
        environment = dict(os.environ, CLAUDE_CODE_SESSION_ID="0000-session", FACTORY_SESSION_USAGE="off")
        out = subprocess.run([sys.executable, args.gate, "--stage-end", "plan", "--story", "S-1"], cwd=root,
                             env=environment, capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("usage in a session: FACTORY_SESSION_USAGE=off records the stage as unknown and "
                             "no session", "switched off" in out and "session=" not in open(journal, encoding="utf-8").read(),
                             out.strip()))
        with open(os.path.join(root, ".agents", "factory", "factory.profile.yaml") if os.path.isdir(
                os.path.join(root, ".agents", "factory")) else os.path.join(root, "factory.profile.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write("sessionUsage: off\n")
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:06:00.000Z\tstage-start\ttest\ttool=claude-session\n")
        out = subprocess.run([sys.executable, args.gate, "--stage-end", "test", "--story", "S-1"], cwd=root,
                             env=dict(os.environ, CLAUDE_CODE_SESSION_ID="0000-session"), capture_output=True,
                             text=True, encoding="utf-8").stdout
        expectations.append(("usage in a session: `sessionUsage: off` in the profile does the same for the project",
                             "switched off" in out, out.strip()))
    with tmpdir() as root:
        # Codex: found by the id in its file name; no other session's log is opened
        codex_home = os.path.join(root, "codex-home")
        day = os.path.join(codex_home, "sessions", "2026", "09", "23")
        os.makedirs(day)
        entry = lambda stamp, out: json.dumps({"timestamp": stamp, "type": "event_msg", "payload": {
            "type": "token_count", "info": {"total_token_usage": {"input_tokens": 100, "cached_input_tokens": 0,
                                                                  "output_tokens": out}}}})
        with open(os.path.join(day, "rollout-2026-09-23T10-00-00-abc-123.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(entry("2026-09-23T10:02:00.000Z", 7) + "\n")
        with open(os.path.join(day, "rollout-2026-09-23T10-00-00-other-999.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("not json — a log that must not be opened\n")
        journal = os.path.join(root, "tasks", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:01:00.000Z\tstage-start\tplan\ttool=codex-session\n"
                         "2026-09-23T10:03:00.000Z\tusage\tplan\ttool=codex-session\t"
                         "window=2026-09-23T10:01:00.000Z/2026-09-23T10:03:00.000Z\tsession=codex:abc-123\n")
        report = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                env=dict(os.environ, CODEX_HOME=codex_home), capture_output=True, text=True,
                                encoding="utf-8").stdout
        row = next((l for l in report.splitlines() if l.startswith("S-1/plan")), "")
        expectations.append(("usage in a session: a Codex session is found by its id alone",
                             row.split()[1:3] == ["1", "1"] and row.split()[6] == "7", row))
    with tmpdir() as root:
        # a union merge: one branch read the window, the other still points at the log; lines interleave
        journal = os.path.join(root, "tasks", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        window = "window=2026-09-23T10:00:00.000Z/2026-09-23T10:05:00.000Z"
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:05:00.000Z\tstage-end\tplan\texit=0\n"
                         f"2026-09-23T10:05:00.000Z\tusage\tplan\ttool=claude-session\tmodel=m\tinput=1\t"
                         f"cache_read=0\tcache_write=0\toutput=9\t{window}\n"
                         f"2026-09-23T10:05:00.000Z\tusage\tplan\ttool=claude-session\t{window}\tlog=/gone.jsonl\n"
                         "2026-09-23T10:00:00.000Z\tstage-start\tplan\ttool=claude-session\n")
        report = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        status_out = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace").stdout
        row = next((l for l in report.splitlines() if l.startswith("S-1/plan")), "")
        expectations.append(("usage after a union merge: one window read on one branch and pending on the other "
                             "counts once", row.split()[1:3] == ["1", "1"] and row.split()[6] == "9", row))
        expectations.append(("status after a union merge: a stage is running only if its start is the latest "
                             "event by time, not by line", "S-1  stage plan" not in status_out,
                             status_out.split("== waiting")[0]))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- one worker per checkout: the claim, and what the schedule does with a running stage -----------
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        claim = lambda owner, *more: subprocess.run([sys.executable, args.gate, "--claim", owner], cwd=root,
                                                    env=dict(os.environ, **dict(more)), capture_output=True,
                                                    text=True, encoding="utf-8")
        first, second, again = claim("worker-a"), claim("worker-b"), claim("worker-a")
        taken = claim("worker-b", ("FACTORY_STALE_AFTER", "0"))
        lock_in_git = os.path.isfile(os.path.join(root, ".git", "dca-factory-worker.lock"))
        subprocess.run([sys.executable, args.gate, "--release", "worker-b"], cwd=root, capture_output=True)
        expectations = [
            ("claim: the first worker takes the checkout, the second is refused and told who holds it",
             first.returncode == 0 and second.returncode == 3 and "held by worker-a" in second.stdout, second.stdout),
            ("claim: the holder renews its own claim", again.returncode == 0, again.stdout),
            ("claim: a holder with no sign of life is taken over, and that is said",
             taken.returncode == 0 and "took over from worker-a" in taken.stdout, taken.stdout),
            ("claim: it lives in the git directory, so it is never committed and never drift",
             lock_in_git, os.listdir(os.path.join(root, ".git"))[:6]),
            ("claim: the holder gives it back", not os.path.exists(os.path.join(root, ".git", "dca-factory-worker.lock")), ""),
        ]
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        environment = dict(os.environ, CLAUDE_CODE_SESSION_ID="listening-session")
        before = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True, text=True,
                                encoding="utf-8").stdout
        subprocess.run([sys.executable, args.gate, "--listening"], cwd=root, env=environment, capture_output=True)
        after = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8").stdout
        ended = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", env=dict(os.environ, FACTORY_LISTEN_STALE="60")).stdout
        brief = subprocess.run([sys.executable, args.gate, "--status", "--brief"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8").stdout
        expectations += [
            ("listening: before any look the status says no session has looked",
             "no session has looked at the backlog" in before, before.split("== waiting")[0]),
            ("listening: a look is shown with the session and how long ago",
             "listening: claude-session:listening-session, last look 0 min ago" in after
             and "listening:" in brief, after.split("== waiting")[0]),
            ("listening: it lives in the git directory, never committed",
             os.path.isfile(os.path.join(root, ".git", "dca-factory-listener.json")), ""),
        ]
        write_old = os.path.join(root, ".git", "dca-factory-listener.json")
        data = json.load(open(write_old, encoding="utf-8"))
        data["beat"] = "2026-01-01T00:00:00Z"
        json.dump(data, open(write_old, "w", encoding="utf-8"))
        old = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True, text=True,
                             encoding="utf-8").stdout
        expectations.append(("listening: a long silence reads as a loop that has probably ended",
                             "probably ended" in old, old.split("== waiting")[0]))
    with tmpdir() as root:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        backlog_project(root, ("STORY-2", []), extra_sources=(
            ("tasks/STORY-1/plan.md", PLAN_APPLIED),
            ("tasks/STORY-1/.verify/journal.tsv", f"{now}\tstage-start\ttest\ttool=x\n"),))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a stage that started and has not ended is running, and nothing else starts",
                             rows.get("STORY-1", ("",))[0] == "running" and nxt.startswith("none")
                             and "STORY-1 is running" in nxt, f"{rows.get('STORY-1')}, next: {nxt}"))
        completed = subprocess.run([sys.executable, args.gate, "--schedule"], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", env=dict(os.environ, FACTORY_STALE_AFTER="0"))
        expectations.append(("schedule: a start with no sign of life is taken as interrupted, and the story is "
                             "named again", "possibly interrupted" in completed.stdout
                             and "next: STORY-1" in completed.stdout, completed.stdout.strip().splitlines()[-1:]))
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run([sys.executable, args.gate, "--claim", "someone-else"], cwd=root, capture_output=True)
        out = subprocess.run([sys.executable, args.gate, "--stage-start", "plan", "--story", "STORY-1"], cwd=root,
                             env=dict(os.environ, CLAUDE_CODE_SESSION_ID="this-session"), capture_output=True,
                             text=True, encoding="utf-8")
        expectations.append(("claim: a session's stage mark is refused while another worker holds the checkout",
                             out.returncode == 3 and not os.path.exists(
                                 os.path.join(root, "tasks", "STORY-1", ".verify", "journal.tsv")), out.stdout))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- existing tests keep their expectations: the plan gate's baseline, the later gates' check -----
    print()
    kept_failures, expectations = [], []

    def kept_verdict(root):
        output = subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "test"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        verdicts = checks_by_verdict(output)
        return ("pass" if "tests-kept" in verdicts["pass"] else "fail" if "tests-kept" in verdicts["fail"]
                else "skip" if "tests-kept" in verdicts["skip"] else "absent"), output

    unit = os.path.join("src", "test", "java", "com", "example", "WidgetUnitTest.java")
    old_test = "class WidgetUnitTest {\n  void showsNothingWhenEmpty() { assert list.isEmpty(); }\n}\n"
    changed_line = lambda t: t.replace("isEmpty()", "size() == 0 || true")
    listing = ("## Changed tests\n| Test file | Backed by |\n| --- | --- |\n"
               "| `src/test/java/com/example/WidgetUnitTest.java` | {backing} |\n")
    says = "\n## Changed expectations\n\n- An empty list now reads as zero things, not as an error.\n"
    for label, story_extra, plan_extra, record, expected in (
            ("A: the story says what changes and the plan lists the test — the change passes",
             says, listing.format(backing="the story's changed expectation"), None, "pass"),
            ("a listed test without a story line or an answered decision is refused",
             "", listing.format(backing="the plan thinks so"), None, "fail"),
            ("the story says what changes, but a test the plan does not list is still refused",
             says, "", None, "fail"),
            ("the template's prose and `{{…}}` placeholder under `## Changed expectations` back nothing",
             "\n## Changed expectations\n\nOnly when the story changes behaviour the system already has.\n\n"
             "- {{WHAT_CHANGES}}\n", listing.format(backing="the story's changed expectation"), None, "fail"),
            ("B: the plan asked once, the row cites the answered decision — the change passes",
             "", listing.format(backing="decision STORY-1-01"), DECISION + ANSWER, "pass")):
        with tmpdir() as root:
            build_project(root, story=STORY.replace("\n## Assumptions", story_extra + "\n## Assumptions"),
                          extra_sources=((unit, old_test),))
            for command in (["init", "-q"], ["add", "-A"],
                            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
                subprocess.run(["git", *command], cwd=root, capture_output=True)
            subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
            with open(os.path.join(root, "tasks", "STORY-1", "plan.md"), "w", encoding="utf-8") as handle:
                handle.write(PLAN_APPLIED + "\n" + plan_extra)
            if record:
                os.makedirs(os.path.join(root, ".agents", "factory", "decisions"), exist_ok=True)
                with open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"), "w",
                          encoding="utf-8") as handle:
                    handle.write(record)
            with open(os.path.join(root, unit), "w", encoding="utf-8") as handle:
                handle.write(changed_line(old_test))
            verdict, output = kept_verdict(root)
            expectations.append((f"tests-kept: {label}", verdict == expected,
                                 f"verdict {verdict}; " + "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    for label, change, decided, expected in (
            ("change: a case added to an existing test file keeps what it expected",
             lambda t: t.replace("}\n}", "}\n  void showsOne() { assert list.size() == 1; }\n}"), False, "pass"),
            ("an existing test whose assertion changed is refused without a decision",
             lambda t: t.replace("isEmpty()", "size() == 0 || true"), False, "fail"),
            ("an existing test that was removed is refused without a decision", None, False, "fail"),
            ("an added skip marker on an existing test is refused, though every old line is kept",
             lambda t: t.replace("  void showsNothing", "  @Disabled\n  void showsNothing"), False, "fail"),
            ("an added block comment around an existing test is refused, though every old line is kept",
             lambda t: t.replace("  void showsNothing", "  /*\n  void showsNothing").replace("}\n}\n", "}\n  */\n}\n"),
             False, "fail"),
            ("a new case with its own doc comment still only adds",
             lambda t: t.replace("}\n}", "}\n  /** One thing. */\n  void showsOne() { assert list.size() == 1; }\n}"),
             False, "pass"),
            ("the same changed assertion passes on an answered decision of the test stage",
             lambda t: t.replace("isEmpty()", "size() == 0 || true"), True, "pass")):
        with tmpdir() as root:
            build_project(root, extra_sources=((unit, old_test),))
            for command in (["init", "-q"], ["add", "-A"],
                            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
                subprocess.run(["git", *command], cwd=root, capture_output=True)
            subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
            baseline = os.path.isfile(os.path.join(root, "tasks", "STORY-1", ".tests-baseline"))
            if change is None:
                os.remove(os.path.join(root, unit))
            else:
                with open(os.path.join(root, unit), "w", encoding="utf-8") as handle:
                    handle.write(change(old_test))
            if decided:
                os.makedirs(os.path.join(root, ".agents", "factory", "decisions"), exist_ok=True)
                with open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"), "w",
                          encoding="utf-8") as handle:
                    handle.write(CONFLICT + ANSWER)
                with open(os.path.join(root, "tasks", "STORY-1", "tests.md"), "w", encoding="utf-8") as handle:
                    handle.write(TESTS_ON_DECISION)
            verdict, output = kept_verdict(root)
            expectations.append((f"tests-kept: {label.replace('change: ', '')}", baseline and verdict == expected,
                                 f"baseline {baseline}, verdict {verdict}; "
                                 + "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    with tmpdir() as root:
        build_project(root, extra_sources=((unit, old_test),))
        for command in (["init", "-q"], ["add", "-A"],
                        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        baseline = os.path.join(root, "tasks", "STORY-1", ".tests-baseline")
        with open(baseline, encoding="utf-8") as handle:
            text = re.sub(r"^[0-9a-f]{40}", "0" * 40, handle.read(), flags=re.M)
        with open(baseline, "w", encoding="utf-8") as handle:
            handle.write(text)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: a baseline blob that is gone is skipped and named, not passed in silence",
                             "gate:skip tests-kept" in output and "pruned" in output,
                             "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    with tmpdir() as root:
        build_project(root)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: outside a git repository the check is skipped and named",
                             verdict == "skip", verdict))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            kept_failures.append(name)
    failures += [(name, [], "") for name in kept_failures]

    # --- the schedule: every story's state and the next one, from the files alone -------------
    print()
    schedule_failures = []
    expectations = []
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", ["STORY-1"]), ("STORY-3", []), ("STORY-4", ["STORY-5"]),
                        ("STORY-5", ["STORY-4"]), ("STORY-6", ["STORY-9"]), ("STORY-7", []),
                        extra_sources=(("tasks/STORY-1/document.md", DOCUMENT),
                                       ("tasks/STORY-1/.delivered", "2026-09-23T00:00:00Z\n"),
                                       ("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                       ("tasks/STORY-3/plan.md", PLAN_ASKING.replace("STORY-1", "STORY-3")),
                                       (".agents/factory/decisions/STORY-3-01.md",
                                        DECISION.replace("STORY-1", "STORY-3"))))
        with open(os.path.join(root, "backlog", "sample", "STORY-7.md"), "w", encoding="utf-8") as handle:
            handle.write(story("STORY-7", status="draft"))
        with open(os.path.join(root, "backlog", "README.md"), "w", encoding="utf-8") as handle:
            handle.write("# Backlog\n\nOne folder per epic.\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations += [
            ("schedule: a story with its document written is delivered",
             rows.get("STORY-1") == ("delivered", None), rows.get("STORY-1")),
            ("schedule: a story whose dependency is delivered is ready, from plan",
             rows.get("STORY-2") == ("ready", "plan"), rows.get("STORY-2")),
            ("schedule: an open decision record makes its story wait",
             rows.get("STORY-3", ("",))[0] == "waiting", rows.get("STORY-3")),
            ("schedule: a dependency cycle is reported, not followed",
             rows.get("STORY-4", ("",))[0] == "blocked" and rows.get("STORY-5", ("",))[0] == "blocked"
             and "cycle" in output, [l for l in output.splitlines() if "STORY-4" in l]),
            ("schedule: a dependency on an unknown story blocks it",
             rows.get("STORY-6", ("",))[0] == "blocked" and "unknown STORY-9" in output, rows.get("STORY-6")),
            ("schedule: a file beside the epic folders is not a story",
             "README" not in rows, sorted(rows)),
            ("schedule: a draft story is not scheduled",
             rows.get("STORY-7", ("",))[0] == "unreleased", rows.get("STORY-7")),
            ("schedule: the next story runs past one that waits at its plan stage",
             nxt == "STORY-2 plan" and wait == "yes", f"next: {nxt}, wait: {wait}"),
        ]
    with tmpdir() as root:
        # STORY-1 got past its plan stage and waits on a question from its test stage: its tests are
        # in the working tree, so an independent story may not start on top of them.
        backlog_project(root, ("STORY-2", []),
                        extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                       ("tasks/STORY-1/tests.md", TESTS + "\n## needs-human\ndecision: STORY-1-01\n"),
                                       (".agents/factory/decisions/STORY-1-01.md",
                                        DECISION.replace("stage: plan", "stage: test"))))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a waiting story with code in the tree holds the checkout",
                             nxt.startswith("none") and "STORY-1 holds unfinished code" in nxt
                             and rows.get("STORY-2") == ("ready", "plan") and wait == "yes",
                             f"next: {nxt}"))
        with open(os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md"), "a",
                  encoding="utf-8") as handle:
            handle.write(ANSWER)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: once answered, the holder resumes at the stage that asked",
                             rows.get("STORY-1") == ("resumable", "test") and nxt == "STORY-1 test",
                             f"{rows.get('STORY-1')}, next: {nxt}"))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                             ("tasks/STORY-1/tests.md", TESTS),
                                             ("tasks/STORY-1/build.md", "## Changed\n"),
                                             ("tasks/STORY-1/.gate-build.txt", "gate:fail tests-green\n")))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a refused gate sends its story back to that stage",
                             rows.get("STORY-1") == ("in-progress", "build"), rows.get("STORY-1")))
        with open(os.path.join(root, "tasks", "STORY-1", ".rounds"), "w", encoding="utf-8") as handle:
            handle.write("3\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: three rounds stop the story, and nothing waits for them",
                             rows.get("STORY-1", ("",))[0] == "stopped" and nxt.startswith("none")
                             and wait == "no", f"{rows.get('STORY-1')}, next: {nxt}, wait: {wait}"))
    with tmpdir() as root:
        # the marks the gates leave: the plan gate records the story it let through, the document gate
        # that it passed — and the schedule reads both
        backlog_project(root, extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                             ("tasks/STORY-1/tests.md", TESTS),
                                             ("tasks/STORY-1/document.md", DOCUMENT)))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a document file without its gate's mark is not delivered",
                             rows.get("STORY-1") == ("in-progress", "document"), rows.get("STORY-1")))
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "document"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: the document gate's pass is what makes a story delivered",
                             rows.get("STORY-1") == ("delivered", None)
                             and os.path.isfile(os.path.join(root, "tasks", "STORY-1", ".delivered")),
                             rows.get("STORY-1")))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),))
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        unchanged = rows.get("STORY-1")
        with open(os.path.join(root, "backlog", "sample", "STORY-1.md"), "a", encoding="utf-8") as handle:
            handle.write("- answered: archived things are hidden (the-expert, 2026-09-23).\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a story edited after its plan runs from plan again",
                             unchanged == ("in-progress", "test") and rows.get("STORY-1") == ("in-progress", "plan")
                             and "the story changed after it was planned" in output,
                             f"before the edit {unchanged}, after {rows.get('STORY-1')}"))
    with tmpdir() as root:
        # a judge's story conflict: waits, resumes where the answer lands, then runs the rest again
        backlog_project(root, extra_sources=(
            ("tasks/STORY-1/plan.md", PLAN_APPLIED), ("tasks/STORY-1/tests.md", TESTS),
            ("tasks/STORY-1/build.md", "## Changed\n"), ("tasks/STORY-1/tidy.md", "## Moves\n"),
            ("tasks/STORY-1/judge.md", JUDGE_CONFLICT),
            (".agents/factory/decisions/STORY-1-01.md", CONFLICT)))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        waiting = rows.get("STORY-1")
        record = os.path.join(root, ".agents", "factory", "decisions", "STORY-1-01.md")
        with open(record, "a", encoding="utf-8") as handle:
            handle.write(ANSWER)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        resumable = rows.get("STORY-1")
        with open(os.path.join(root, "tasks", "STORY-1", "tests.md"), "w", encoding="utf-8") as handle:
            handle.write(TESTS_ON_DECISION)
        with open(record, "a", encoding="utf-8") as handle:
            handle.write("\n## Applied\nat: 2026-09-23T08:00:00Z\nstage: test\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a judge's story conflict waits, resumes where its answer lands, then "
                             "runs the stages after it again",
                             waiting[0] == "waiting" and resumable == ("resumable", "test")
                             and rows.get("STORY-1") == ("in-progress", "build"),
                             f"open {waiting}, answered {resumable}, applied {rows.get('STORY-1')}"))
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", []), extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),
                                                             ("tasks/STORY-1/tests.md", TESTS)))
        path = os.path.join(root, "backlog", "sample", "STORY-1.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("status: approved", "status: superseded")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a superseded story holds the checkout for nobody, tests or not",
                             rows.get("STORY-1", ("",))[0] == "superseded" and nxt == "STORY-2 plan", f"next: {nxt}"))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("tasks/STORY-1/.gate-plan.txt", "gate:fail epic\n"),))
        refused = os.path.join(root, "tasks", "STORY-1", ".gate-plan.txt")
        os.utime(refused, (time.time() - 60, time.time() - 60))
        story_file = os.path.join(root, "backlog", "sample", "STORY-1.md")
        for name in ("STORY-1.md", "epic.md"):
            os.utime(os.path.join(root, "backlog", "sample", name), (time.time() - 120, time.time() - 120))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        stopped = rows.get("STORY-1")
        os.utime(story_file, None)                              # repaired after the refusal
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a story the plan gate refused runs from plan again once it was repaired",
                             stopped[0] == "stopped" and rows.get("STORY-1") == ("in-progress", "plan"),
                             f"before {stopped}, after {rows.get('STORY-1')}"))
    with tmpdir() as root:
        os.makedirs(os.path.join(root, "tasks", "S-1", ".verify"))
        journal = os.path.join(root, "tasks", "S-1", ".verify", "journal.tsv")
        line = "2026-01-01T00:00:00Z\tusage\tbuild\ttool=claude-session\twindow=2026-01-01T00:00:00Z/2026-01-01T00:01:00Z\tsession=claude:abc\n"
        write_file(root, "tasks/S-1/.verify/journal.tsv", "2026-01-01T00:00:00Z\tstage-start\tbuild\ttool=claude-session\n" + line)
        before = open(journal, encoding="utf-8").read()
        home = os.path.join(root, "home")
        write_file(home, "projects/p/abc.jsonl", json.dumps({"timestamp": "2026-01-01T00:00:30Z", "type": "assistant",
                   "message": {"id": "m1", "model": "x", "usage": {"input_tokens": 5, "output_tokens": 7}}}) + "\n")
        subprocess.run([sys.executable, args.gate, "--usage"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", env=dict(os.environ, CLAUDE_CONFIG_DIR=home))
        expectations.append(("usage: `--usage` only reads — the journal is not rewritten",
                             open(journal, encoding="utf-8").read() == before, ""))
    with tmpdir() as root:
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        write_file(root, ".git/dca-factory-worker.lock", "")
        taken = subprocess.run([sys.executable, args.gate, "--claim", "someone"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8")
        expectations.append(("claim: a claim file that cannot be read yet is aged by its file, not taken over on sight",
                             taken.returncode == 3, taken.stdout.strip()))
    # --- what a story changed: the record and the diff a stage is handed, in a repository without a commit
    with tmpdir() as root:
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        for name, text in (("src/A.txt", "a\n"), ("src/B.txt", "b\n")):
            os.makedirs(os.path.join(root, "src"), exist_ok=True)
            with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        mark = lambda edge: subprocess.run([sys.executable, args.gate, f"--stage-{edge}", "build", "--story", "S-1"],
                                           cwd=root, capture_output=True, text=True, encoding="utf-8",
                                           env=dict(os.environ, FACTORY_SESSION_USAGE="off"))
        mark("start")
        with open(os.path.join(root, "src", "A.txt"), "w", encoding="utf-8") as handle:
            handle.write("a, changed\n")
        with open(os.path.join(root, "src", "C.txt"), "w", encoding="utf-8") as handle:
            handle.write("c\n")
        os.remove(os.path.join(root, "src", "B.txt"))
        os.makedirs(os.path.join(root, "tasks", "S-1"), exist_ok=True)
        with open(os.path.join(root, "tasks", "S-1", "build.md"), "w", encoding="utf-8") as handle:
            handle.write("## Files\n")                      # a run artefact: never part of the change
        mark("end")
        folder = os.path.join(root, "tasks", "S-1", ".verify")
        read = lambda name: open(os.path.join(folder, name), encoding="utf-8").read() if os.path.isfile(
            os.path.join(folder, name)) else ""
        expectations += [
            ("changes: a stage's added, changed and removed files are recorded, run artefacts left out",
             sorted(read("changed-build.txt").splitlines()) == ["added\tsrc/C.txt", "modified\tsrc/A.txt",
                                                                "removed\tsrc/B.txt"],
             read("changed-build.txt")),
            ("changes: the story's record sums its stages", sorted(read("changed.txt").splitlines()) ==
             ["added\tsrc/C.txt", "modified\tsrc/A.txt", "removed\tsrc/B.txt"], read("changed.txt")),
            ("changes: a repository without a commit still gets the story's diff",
             "+a, changed" in read("story.diff") and "src/C.txt" in read("story.diff")
             and "src/B.txt" in read("story.diff") and "build.md" not in read("story.diff"), read("story.diff")[:300]),
        ]
    commit = lambda root: [subprocess.run(["git", *command], cwd=root, capture_output=True) for command in (
        ["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"])]
    marker = lambda cwd, stage, edge: subprocess.run(
        [sys.executable, args.gate, f"--stage-{edge}", stage, "--story", "S-1"], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", env=dict(os.environ, FACTORY_SESSION_USAGE="off"))
    rows_of = lambda cwd, name: sorted(open(os.path.join(cwd, "tasks", "S-1", ".verify", name),
                                            encoding="utf-8").read().splitlines()) \
        if os.path.isfile(os.path.join(cwd, "tasks", "S-1", ".verify", name)) else []
    with tmpdir() as root:
        for name in ("A", "B", "D"):
            write_file(root, f"src/{name}.txt", name.lower() + "\n")
        commit(root)
        write_file(root, "src/D.txt", "d, dirty before the stage\n")
        marker(root, "build", "start")
        write_file(root, "src/A.txt", "a, changed\n")
        write_file(root, "src/C.txt", "c\n")
        write_file(root, "src/D.txt", "d\n")
        os.remove(os.path.join(root, "src", "B.txt"))
        marker(root, "build", "end")
        want = ["added\tsrc/C.txt", "modified\tsrc/A.txt", "modified\tsrc/D.txt", "removed\tsrc/B.txt"]
        expectations += [
            ("changes: after a commit, a deleted tracked file is removed, a clean one edited is modified, a dirty "
             "one put back is modified", rows_of(root, "changed-build.txt") == want, rows_of(root, "changed-build.txt")),
            ("changes: the story's record says the same, from the tree recorded at its first stage",
             rows_of(root, "changed.txt") == want, rows_of(root, "changed.txt")),
        ]
    with tmpdir() as root:
        write_file(root, "src/A.txt", "a\n")
        commit(root)
        marker(root, "plan", "start")
        write_file(root, "src/E.txt", "first pass\n")
        marker(root, "plan", "end")
        marker(root, "plan", "start")                                 # the stage runs again
        write_file(root, "src/F.txt", "second pass\n")
        marker(root, "plan", "end")
        diff = open(os.path.join(root, "tasks", "S-1", ".verify", "story.diff"), encoding="utf-8").read()
        expectations.append(("changes: a stage run again keeps the first pass in the story's record and diff",
                             rows_of(root, "changed.txt") == ["added\tsrc/E.txt", "added\tsrc/F.txt"]
                             and "first pass" in diff, rows_of(root, "changed.txt")))
    with tmpdir() as root:
        write_file(root, "other/X.txt", "x\n")
        write_file(root, "project/src/A.txt", "a\n")
        commit(root)
        project = os.path.join(root, "project")
        marker(project, "build", "start")
        write_file(root, "project/src/A.txt", "a, changed\n")
        write_file(root, "other/X.txt", "x, outside the project\n")
        marker(project, "build", "end")
        diff = open(os.path.join(project, "tasks", "S-1", ".verify", "story.diff"), encoding="utf-8").read()
        expectations.append(("changes: a project inside a larger repository gets its own paths, and nothing "
                             "outside it", rows_of(project, "changed-build.txt") == ["modified\tsrc/A.txt"]
                             and rows_of(project, "changed.txt") == ["modified\tsrc/A.txt"]
                             and "+a, changed" in diff and "X.txt" not in diff,
                             f"{rows_of(project, 'changed-build.txt')} / {rows_of(project, 'changed.txt')}"))
    with tmpdir() as root:
        mark = lambda edge: subprocess.run([sys.executable, args.gate, f"--stage-{edge}", "plan", "--story", "S-1"],
                                           cwd=root, capture_output=True, text=True, encoding="utf-8",
                                           env=dict(os.environ, FACTORY_SESSION_USAGE="off"))
        mark("start"); mark("end")
        diff = os.path.join(root, "tasks", "S-1", ".verify", "story.diff")
        expectations.append(("changes: outside a repository there is no diff, and the file says so",
                             os.path.isfile(diff) and "no diff" in open(diff, encoding="utf-8").read(), ""))

    # --- the product scope before the first story, checked without a story ---------------------------
    with tmpdir() as root:
        product = lambda: subprocess.run([sys.executable, args.gate, "--product"], cwd=root,
                                         capture_output=True, text=True, encoding="utf-8")
        none = product()
        os.makedirs(os.path.join(root, "backlog"))
        with open(os.path.join(root, "backlog", "product.md"), "w", encoding="utf-8") as handle:
            handle.write(PRODUCT.replace("## Surfaces\n\nOne web page, desktop and phone.\n", "## Surfaces\n\n"))
        incomplete = product()
        with open(os.path.join(root, "backlog", "product.md"), "w", encoding="utf-8") as handle:
            handle.write(PRODUCT)
        complete = product()
        expectations.append(("product: `--product` exits 3 without a scope, 1 when a heading is empty, 0 when "
                             "it stands", (none.returncode, incomplete.returncode, complete.returncode) == (3, 1, 0)
                             and "/factory-scope" in none.stdout,
                             f"exits {none.returncode}/{incomplete.returncode}/{complete.returncode}; {none.stdout.strip()}"))
    # --- the pipeline's texts carry no sample vocabulary ----------------------------------------------
    skills_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    vocabulary = re.compile(r"\b(cart|basket|timer|pricing|e-?commerce|breakstarted|work interval)\b", re.I)
    hits = []
    for folder, _, names in os.walk(skills_root):
        for name in names:
            if name.endswith((".md", ".tmpl")):
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if vocabulary.search(line):
                            hits.append(f"{os.path.relpath(path, skills_root)}:{number}")
    expectations.append(("vocabulary: no skill, reference or template names a sample's domain",
                         not hits, ", ".join(hits[:5])))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        if not ok:
            print(f"          {detail}")
            schedule_failures.append(name)
    failures += [(name, [], "") for name in schedule_failures]

    runner_failures = []
    if os.path.isfile(args.runner):
        print()
        runner_failures = verify_runner(args.runner, args.verbose)
    else:
        print(f"verify: no runner at {args.runner} — its cases were skipped")

    if failures or runner_failures:
        print(f"\nverify: FAILED — {len(failures)} gate case(s), {len(runner_failures)} runner case(s)")
        return 1
    print("\nverify: the factory behaves as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
