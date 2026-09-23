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
                           capture_output=True, text=True)
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
        '  build) printf "## Changed\\n## Criteria\\n## Checks\\n" ;; '
        '  tidy) printf "## Moves\\n## Checks\\n" ;; '
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
  build) printf '## Changed\\n' > "$d/build.md" ;;
  tidy) printf '## Moves\\n' > "$d/tidy.md" ;;
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
                                       ("fixture/tests.md", TESTS)))
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
                                 "--usage", "--story", "STORY-2"], cwd=root, capture_output=True, text=True).stdout
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
                                 "--usage", "--story", "STORY-2"], cwd=root, capture_output=True, text=True).stdout
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
        check("update: a tool that had links keeps links, and no tool is added",
              os.path.islink(os.path.join(root, ".codex", "skills", "factory-run")) and "factory-run" in entries
              and not os.path.exists(os.path.join(root, ".opencode")), sorted(entries)[:4])
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
        run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in", "--from", "judge",
                   env={"FACTORY_TOOL_CMD": 'mkdir -p tasks/STORY-1; printf "## Verdict\\nverdict: pass\\n" '
                                            '> tasks/STORY-1/judge.md'})
        snap = read_snapshot(os.path.join(root, "tasks", "STORY-1", ".verify", "tree-before-judge.txt"))
        check("snapshot: a file inside a directory this run added is hashed, not skipped",
              "src/brand-new/Added.java" in snap,
              f"{len(snap)} entries: {sorted(snap)[:4]}…")

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
                cwd=root, capture_output=True, text=True).stdout.strip()
            check(f"runner: reads the verdict '{verdict}' from the file", parsed == expect,
                  f"parsed {parsed!r}")

    # 4. the round counter is a file, and it counts up
    with tmpdir() as root:
        os.makedirs(os.path.join(root, "tasks", "STORY-1"))
        counted = subprocess.run(
            [BASH, "-c",
             f'TASKS=tasks; sed -n "/^bump_rounds/,/^}}/p" "{shell_path(runner)}" > fn.sh; '
             f'. ./fn.sh; bump_rounds STORY-1; bump_rounds STORY-1'],
            cwd=root, capture_output=True, text=True).stdout.split()
        check("runner: the round counter is a file and counts up", counted == ["1", "2"],
              f"got {counted}")

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
        (Case("build: without a policy the build gate runs only the story's tests, as before", "build", 0,
              must_pass=("tests-green",)),
         dict(green=both_green, ledger=both_green)),
        (Case("document: an empty `## needs-human` left from the template stops nothing", "document", 0,
              must_pass=("documented",)),
         dict(document=DOCUMENT + "\n## needs-human\n(none)\n")),
        (Case("test: a test recorded red before may be green when its expectation changed on a decision",
              "test", 0, must_pass=("tests-red", "decisions"), text=("expectation changed on decision STORY-1-01",)),
         dict(tests=TESTS_ON_DECISION, green=both_green, ledger=both_green,
              **with_decisions(("STORY-1-01", CONFLICT + ANSWER), plan=PLAN_APPLIED))),
        (Case("test: without that decision, green before the build is still refused", "test", 1,
              must_fail=("tests-red",), text=("passes before the build stage",)),
         dict(green=both_green, ledger=both_green)),
        # --- the build gate -----------------------------------------------
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
        log = subprocess.run(["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True).stdout.split()
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
                response("2026-09-23T10:01:00.000Z", "m1", 50),                     # in it, three blocks
                response("2026-09-23T10:01:00.100Z", "m1", 50),
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
                       env=environment, capture_output=True, text=True)
        lines = open(journal, encoding="utf-8").read().splitlines()
        recorded = [l for l in lines if "\tusage\t" in l]
        if recorded:
            fixed = recorded[0].split("\t")
            fixed = [("window=2026-09-23T10:00:30.000Z/2026-09-23T10:05:00.000Z" if f.startswith("window=") else f)
                     for f in fixed]
            with open(journal, "w", encoding="utf-8") as handle:
                handle.write("\n".join(l for l in lines if "\tusage\t" not in l) + "\n" + "\t".join(fixed) + "\n")
        report = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                env=environment, capture_output=True, text=True).stdout
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
                               capture_output=True, text=True).stdout
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:01:00.000Z\tstage-start\ttest\ttool=codex-session\n"
                         f"2026-09-23T10:03:00.000Z\tusage\ttest\ttool=codex-session\t"
                         f"window=2026-09-23T10:01:00.000Z/2026-09-23T10:03:00.000Z\tlog={rollout}\n")
        report2 = subprocess.run([sys.executable, args.gate, "--usage", "--story", "S-1"], cwd=root,
                                 capture_output=True, text=True).stdout
        test_row = next((l for l in report2.splitlines() if l.startswith("S-1/test")), "")
        expectations = [
            ("usage in a session: the mark records the window and the log, not a number the log lags behind",
             bool(recorded) and "window=" in recorded[0] and "log=" in recorded[0], recorded[:1]),
            ("usage in a session: Claude's log is read for the window, each response once, subagents included, "
             "synthetic entries left out", row.split()[1:7] == ["1", "1", "2", "200", "20", "57"], row),
            ("usage in a session: a session log has no cost, and the report says so rather than 0.00",
             row.split()[-1:] == ["—"], row),
            ("usage in a session: once read, the numbers are written into the journal and the machine-local "
             "log path leaves it",
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
            ("status: every story's state is there, and the cost in total",
             "STORY-1  waiting" in section("stories") and "2 stage invocation(s), 1 measured, 100 tokens, $0.01"
             in section("cost"), section("cost")),
        ]
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
                                capture_output=True, text=True).stdout
        status_out = subprocess.run([sys.executable, args.gate, "--status"], cwd=root, capture_output=True,
                                    text=True).stdout
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
            ("B: the plan asked once, the row cites the answered decision — the change passes",
             "", listing.format(backing="decision STORY-1-01"), DECISION + ANSWER, "pass")):
        with tmpdir() as root:
            build_project(root, story=STORY.replace("\n## Assumptions", story_extra + "\n## Assumptions"),
                          extra_sources=((unit, old_test),))
            for command in (["init", "-q"], ["add", "-A"],
                            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
                subprocess.run(["git", *command], cwd=root, capture_output=True)
            subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                           capture_output=True, text=True)
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
            ("the same changed assertion passes on an answered decision of the test stage",
             lambda t: t.replace("isEmpty()", "size() == 0 || true"), True, "pass")):
        with tmpdir() as root:
            build_project(root, extra_sources=((unit, old_test),))
            for command in (["init", "-q"], ["add", "-A"],
                            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
                subprocess.run(["git", *command], cwd=root, capture_output=True)
            subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                           capture_output=True, text=True)
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
                       capture_output=True, text=True)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: the document gate's pass is what makes a story delivered",
                             rows.get("STORY-1") == ("delivered", None)
                             and os.path.isfile(os.path.join(root, "tasks", "STORY-1", ".delivered")),
                             rows.get("STORY-1")))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("tasks/STORY-1/plan.md", PLAN_APPLIED),))
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True)
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
