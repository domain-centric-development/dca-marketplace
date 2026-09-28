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
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

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
    Where the shell cannot link, `setup` copies, and the link cases here have no subject."""
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
DEFAULT_CLI = os.path.normpath(os.path.join(HERE, "..", "..", "factory-run", "scripts", "factory-cli.py"))

# Every case's verdict, in the order it ran, for the JUnit report `--junit` writes: (group, name, ok, detail).
RESULTS = []
CURRENT_GROUP = ["checks"]


def note_result(name, ok, detail=""):
    RESULTS.append((CURRENT_GROUP[0], name, ok, detail))


def cli_of(gate):
    """The CLI beside a gate — the file that shows and coordinates; the gate only decides."""
    return os.path.join(os.path.dirname(gate), "factory-cli.py")


def cli_in(root):
    return os.path.join(root, ".agents", "factory", "factory-cli.py")


def copy_scripts(beside, root):
    """The gate and the CLI, into a fixture's .agents/factory — as the install puts them there."""
    folder = os.path.dirname(beside)
    os.makedirs(os.path.join(root, ".agents", "factory"), exist_ok=True)
    for name in ("story-gate.py", "factory-cli.py"):
        shutil.copy(os.path.join(folder, name), os.path.join(root, ".agents", "factory", name))
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
- shows-nothing-when-empty (happy path): With nothing recorded, the reader sees an empty list, not an error.

## Assumptions

- open: Does an archived thing count?
"""

#: The same two criteria in the scenario form: keyed Given/When/Then scenarios under Gherkin rules.
STORY_SCENARIOS = STORY.replace("""- shows-the-thing: The reader sees the thing.
- shows-nothing-when-empty (happy path): With nothing recorded, the reader sees an empty list, not an error.
""", """### Rule: What is recorded is shown

#### shows-the-thing
- Given one thing is recorded
- When the reader opens the list
- Then the list shows the thing

### Rule: An empty record is not an error

#### shows-nothing-when-empty (happy path)
- Given nothing is recorded
- When the reader opens the list
- Then the list is empty
- And no error is shown

## Out of scope

- Sharing things with others.
""")

#: A story describing behaviour the project already has: adopted, never built.
ADOPTED = STORY.replace("status: approved", "status: adopted").replace(" (happy path):", ":")
#: The tests the adoption wrote itself, each shown to work by a break.
CHARACTERIZED = "\n## Characterization\n- com.example.WidgetPageTest#showsTheThing\n"
#: A break the fixture's runner notices: the test's green marker is gone, so the test is red.
BREAK_THE_THING = """diff --git a/green/comexampleWidgetPageTestshowsTheThing b/green/comexampleWidgetPageTestshowsTheThing
deleted file mode 100644
index e69de29..0000000
"""
#: A break that changes something no test reads.
BREAK_NOTHING = """diff --git a/unrelated.txt b/unrelated.txt
--- a/unrelated.txt
+++ b/unrelated.txt
@@ -1 +1 @@
-a
+b
"""

# A test runner whose verdict hangs on production code in a package named like a build output (`tasks`).
PACKAGED_RUN = """#!/bin/sh
set=$1; shift; [ "$1" = "--select" ] && shift; sel=$1
cls=${sel%%#*}; m=${sel##*#}; simple=${cls##*.}
mkdir -p build/test-results/run
if grep -q shown src/main/java/com/example/tasks/Widget.java 2>/dev/null; then
  printf '<testsuite><testcase classname="%s" name="%s"/></testsuite>' "$cls" "$m" > build/test-results/run/TEST-$simple.xml; exit 0
fi
printf '<testsuite><testcase classname="%s" name="%s"><failure>x</failure></testcase></testsuite>' "$cls" "$m" > build/test-results/run/TEST-$simple.xml; exit 1
"""
PACKAGED_PROFILE = ("compile: true\ntest: sh my.sh src/test/java\ntest.pages: sh my.sh src/test-pages/java\n"
                    "filterFlag: --select\nfilterFormat: \"{class}#{method}\"\n")
PACKAGED_SOURCES = (("my.sh", PACKAGED_RUN), ("unrelated.txt", "a\n"), (".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),
                    ("src/main/java/com/example/tasks/Widget.java", "class Widget { String s = \"shown\"; }\n"),
                    (".dca-factory/runs/STORY-1/breaks/com.example.WidgetPageTest--showsTheThing.patch", BREAK_NOTHING))


TESTS = """# Tests — STORY-1

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-the-thing | com.example.WidgetPageTest#showsTheThing |
| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |

## Files
- src/test-pages/java/com/example/WidgetPageTest.java
- src/test/java/com/example/WidgetUnitTest.java
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
if [ -f "timeout/$(echo "$selector" | tr -d './#')" ]; then
  echo "TimeoutError: locator.click: Timeout 30000ms exceeded."
  echo "Call log: waiting for getByRole('button', { name: 'Add' })"
fi
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
TECH = """# Widgets — technical decisions

## Stack

A JVM service built with the project's wrapper.

## Frontend approach

Server-rendered pages, no client framework.

## Persistence

One relational database.

## Runtime

A container.

## Integrations

None.

## Version policy

The generator's versions, kept current.
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


def record_file(name):
    """Where a record with this id lives in the fixture: `<story>.decisions/<nn>.md` beside the story."""
    match = re.match(r"^(.*?)-(accept-\d+|\d+)$", name)
    story, nn = (match.group(1), match.group(2)) if match else (name, name)
    return f"project/epics/sample/{story}.decisions/{nn}.md"


def delivered_story(text, stamp="2026-09-26T07:40:00Z"):
    """The story as the gate leaves it once delivered: `status: delivered` and `delivered:` — an adopted story
    keeps its status and gains the date."""
    if "status: adopted" in text:
        return text.replace("status: adopted", f"status: adopted\ndelivered: {stamp}")
    return text.replace("status: approved", f"status: delivered\ndelivered: {stamp}")


def story_delivered(root, story_id="STORY-1", epic="sample"):
    """Whether the story says it is delivered — the gate's mark, read off the file."""
    path = os.path.join(root, "project", "epics", epic, f"{story_id}.md")
    if not os.path.isfile(path):
        return False
    front = open(path, encoding="utf-8").read().split("---", 2)[1]
    return bool(re.search(r"^status:\s*delivered\s*$", front, re.M) or re.search(r"^delivered:\s*\S", front, re.M))


def mark_delivered(root, story_id="STORY-1", stamp="2026-09-26T07:40:00Z", epic="sample"):
    """Write the gate's delivered mark into the fixture's story."""
    path = os.path.join(root, "project", "epics", epic, f"{story_id}.md")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(delivered_story(text, stamp))


def undeliver(root, story_id="STORY-1", epic="sample"):
    """Take the delivered mark out of the fixture's story again — what a reopen does to the front matter."""
    path = os.path.join(root, "project", "epics", epic, f"{story_id}.md")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    text = re.sub(r"^status: delivered$", "status: approved", text, flags=re.M)
    text = re.sub(r"^delivered:.*\n", "", text, flags=re.M)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def with_decisions(*records, plan=None, **more):
    """A fixture with decision records beside the story and, optionally, a plan."""
    sources = [(record_file(name), text) for name, text in records]
    if plan is not None:
        sources.append((".dca-factory/runs/STORY-1/plan.md", plan))
    fixture = dict(extra_sources=tuple(sources) + tuple(more.pop("extra_sources", ())))
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
    sources = [(f"project/epics/sample/{sid}.md", story(sid, deps)) for sid, deps in stories]
    build_project(root, tests=None, profile="compile: true\n",
                  extra_sources=tuple(sources) + tuple(more.pop("extra_sources", ())), **more)
    return root


def usage_json(gate, root, story, env=None):
    """{stage: figures} of one story's journal, as the status computes them."""
    done = subprocess.run([sys.executable, cli_of(gate), "--usage", "--story", story, "--format", "json"], cwd=root,
                          env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(done.stdout or "{}")
    except ValueError:
        return {}


def schedule_of(gate, root):
    """{story: (state, from)} and the `next:` / `wait:` lines of `story-gate.py --schedule`."""
    listing = subprocess.run([sys.executable, cli_of(gate), "--schedule"], cwd=root, capture_output=True,
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

    def __init__(self, name, stage, expect_exit, must_pass=(), must_fail=(), must_skip=(), text=(), absent=()):
        self.name = name
        self.stage = stage
        self.expect_exit = expect_exit
        self.must_pass = must_pass
        self.must_fail = must_fail
        self.must_skip = must_skip
        self.text = text
        self.absent = absent


def story_digest(path):
    """The story's digest as the plan gate records it: `status:` and `delivered:` left out."""
    text = open(path, encoding="utf-8").read()
    parts = text.split("---", 2)
    kept = [l for l in parts[1].splitlines() if l.split(":", 1)[0].strip().lower() not in ("status", "delivered")]
    return hashlib.sha256(("---" + "\n".join(kept) + "\n---" + parts[2]).encode("utf-8")).hexdigest()


def build_project(root, *, epic=EPIC, story=STORY, tests=TESTS, profile=PROFILE,
                  context_map="# Context map\n\n| Context |\n|---|\n| Widgets |\n",
                  document=None, green=(), rounds=None, ledger=None, extra_sources=(), timeouts=()):
    """A project just large enough for the gate to have something to check."""
    def write(path, content):
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    write("project/epics/sample/epic.md", epic)
    write("project/epics/sample/STORY-1.md", story)
    write("dca-factory.profile.yaml", profile)
    write("AGENTS.md", "# AGENTS.md\n\nA fixture.\n")
    write("README.md", "A fixture project.\n")
    if context_map is not None:
        write("docs/context-map.md", context_map)
    write("src/test/java/com/example/WidgetUnitTest.java",
          "class WidgetUnitTest { void showsNothingWhenEmpty() {} }\n")
    write("src/test-pages/java/com/example/WidgetPageTest.java",
          "class WidgetPageTest { @DisplayName(\"Shows the thing\") void showsTheThing() {} }\n")
    for path, content in extra_sources:
        write(path, content)
    if tests is not None:
        write(".dca-factory/runs/STORY-1/tests.md", tests)
    if document is not None:
        # a document stage comes after a whole pass: every stage's file, a judge's pass, the story as planned
        for name, content in (("plan.md", "# Plan\n"), ("build.md", "# Build\n"), ("tidy.md", "# Tidy\n"),
                              ("judge.md", "## Verdict\nverdict: pass\n"), ("tests.md", TESTS)):
            if not os.path.isfile(os.path.join(root, ".dca-factory/runs/STORY-1", name)):
                write(".dca-factory/runs/STORY-1/" + name, content)
        if not os.path.isfile(os.path.join(root, ".dca-factory/runs/STORY-1/.story-digest")):
            write(".dca-factory/runs/STORY-1/.story-digest", story_digest(os.path.join(root, "project/epics/sample/STORY-1.md")))
        write(".dca-factory/runs/STORY-1/document.md", document)
    if rounds is not None:
        write(".dca-factory/runs/STORY-1/.rounds", str(rounds))
    if ledger is not None:
        write(".dca-factory/runs/STORY-1/.tests-red", "\n".join(ledger) + "\n")
    write("runner.sh", RUNNER_STUB)
    os.chmod(os.path.join(root, "runner.sh"), 0o755)
    write("gradlew-stub", TASK_RUNNER_STUB)
    os.chmod(os.path.join(root, "gradlew-stub"), 0o755)
    for selector in green:
        write("green/" + re.sub(r"[./#]", "", selector), "")
    for selector in timeouts:
        write("timeout/" + re.sub(r"[./#]", "", selector), "")
    return root


def marked_build_outside_git(root, args):
    """A build stage marked by the CLI in a project that is no git repository, with one file changed in
    its window — the in-session tier on a project before its `git init`."""
    env = dict(os.environ, FACTORY_SESSION_USAGE="off")
    subprocess.run([sys.executable, args.cli, "--stage-start", "build", "--story", "STORY-1"], cwd=root,
                   capture_output=True, env=env)
    write_file(root, "src/main/Thing.java", "class Thing {}\n")
    subprocess.run([sys.executable, args.cli, "--stage-end", "build", "--story", "STORY-1"], cwd=root,
                   capture_output=True, env=env)


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
# artefact names, the verdict handling and the two shapes `setup` may leave behind.


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


def in_git(root):
    """`setup` needs a repository (the commit hook and the worker lock live in .git); a fixture gets one."""
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True).returncode:
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)


def run_setup(runner, root, *args, env=None):
    in_git(root)
    return run_runner(runner, root, "setup", *args, env=env)


def verify_runner(runner, verbose=False):
    """Order, names, verdicts, links — everything about the runner that holds without a model."""
    results = []
    both_green = ["com.example.WidgetPageTest#showsTheThing",
                  "com.example.WidgetUnitTest#showsNothingWhenEmpty"]

    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
        if not ok and detail:
            print(f"          {detail}")

    # 1. the stage order, and which gate runs before its stage and which after
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        order = [line.strip()[3:].split("  (")[0].strip()
                 for line in output.splitlines() if line.startswith("── ")]
        expected = ["gate plan", "stage plan", "stage test", "gate test", "stage build",
                    "gate build", "stage tidy", "gate tidy", "stage judge", "stage document",
                    "gate document"]
        check("runner: the plan gate runs before its stage, every other gate after it",
              order == expected, f"got {order}")
        check("runner: a dry run changes nothing", code == 0 and not os.path.isdir(os.path.join(root, ".dca-factory", "runs", "STORY-1", "plan.md")))

    # 1c. an adoption builds nothing: plan, test, judge, then the adopt gate
    with tmpdir() as root:
        build_project(root, story=STORY.replace("status: approved", "status: adopted"))
        copy_scripts(runner, root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        order = [line.strip()[3:].split("  (")[0].strip()
                 for line in output.splitlines() if line.startswith("── ") and "skipped" not in line]
        check("runner: an adopted story runs plan, test and judge — build, tidy and document are skipped",
              order == ["gate plan", "stage plan", "stage test", "gate test", "stage judge"]
              and "stage document  (skipped: an adopted story is not built)" in output, f"got {order}")

    # 1b. a journey walks what is delivered: no build, no tidy
    with tmpdir() as root:
        build_project(root, story=STORY.replace("status: approved\n", "status: approved\nkind: journey\n")
                      .replace("depends_on: []", "depends_on: [STORY-0]"))
        copy_scripts(runner, root)
        # STORY-0 is not in this backlog, so the story is blocked; a named stage runs it anyway.
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "plan", "--tool", "claude",
                                  "--dry-run")
        order = [line.strip()[3:].split("  (")[0].strip()
                 for line in output.splitlines() if line.startswith("── ") and "skipped" not in line]
        check("runner: a journey runs plan, test, judge and document — build and tidy are skipped and said so",
              order == ["gate plan", "stage plan", "stage test", "gate test", "stage judge", "stage document",
                        "gate document"] and "stage build  (skipped: a journey builds nothing)" in output, f"got {order}")

    # 1a. the stage process sees only the project: the isolation flags, one prefix for every stage
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
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
        copy_scripts(runner, root)
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
        copy_scripts(runner, root)
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
        copy_scripts(runner, root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("model: `model.<tool>` is the default for every stage without a key of its own",
              set(models_of(output).values()) == {"--model model-b"} and len(models_of(output)) == 6,
              models_of(output))
    with tmpdir() as root:
        build_project(root, profile=PROFILE.replace("contract: 6", "") + "contract: 99\n")
        copy_scripts(runner, root)
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
        read = subprocess.run([sys.executable, cli_of(gate), "--usage-from", "opencode-json", raw, "--usage-model",
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
        'mkdir -p .dca-factory/runs/STORY-1; '
        'case "$FACTORY_STAGE" in '
        '  plan) printf "## Context\\n## Changes\\n## Acceptance criteria\\n" ;; '
        '  test) cat "$FIXTURE_TESTS" ;; '
        '  build) printf "## Changed\\n## Criteria\\n## Checks\\n## Files\\n"; '
        '    for s in $(cat "$FIXTURE_GREEN" 2>/dev/null); do printf -- "- green/%s\\n" "$s"; done ;; '
        '  tidy) printf "## Moves\\n## Checks\\n## Files\\n" ;; '
        '  judge) printf "## Verdict\\nverdict: pass\\n" ;; '
        '  document) printf "## Glossary\\n" ;; '
        'esac > ".dca-factory/runs/STORY-1/$f"; '
        # red until the build stage, as a real run is: the test gate must see them fail
        'case "$FACTORY_STAGE" in build|tidy|judge|document) '
        '  for s in $(cat "$FIXTURE_GREEN" 2>/dev/null); do mkdir -p green; : > "green/$s"; done ;; '
        'esac'
    )
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        # the stand-in turns the mapped tests green from the build stage onwards
        with open(os.path.join(root, "greens.txt"), "w", encoding="utf-8") as handle:
            handle.write("")
        tests_path = os.path.join(root, "fixture-tests.md")
        with open(tests_path, "w", encoding="utf-8") as handle:
            handle.write(TESTS)
        os.remove(os.path.join(root, ".dca-factory", "runs", "STORY-1", "tests.md"))
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
        journal = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify")
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
    def shared_run(skip_test_gate=False, dry=False, **project):
        with tmpdir() as root:
            build_project(root, **project)
            copy_scripts(runner, root)
            tests_path = os.path.join(root, "fixture-tests.md")
            with open(tests_path, "w", encoding="utf-8") as handle:
                handle.write(TESTS)
            os.remove(os.path.join(root, ".dca-factory", "runs", "STORY-1", "tests.md"))
            with open(os.path.join(root, "greens.txt"), "w", encoding="utf-8") as handle:
                handle.write(" ".join(re.sub(r"[./#]", "", s) for s in both_green) + "\n")
            env = {"FACTORY_TOOL_CMD": builder_cmd, "FIXTURE_STAND_IN": stand_in,
                   "FIXTURE_TESTS": shell_path(tests_path), "FIXTURE_PY": shell_path(sys.executable),
                   "FIXTURE_GREEN": shell_path(os.path.join(root, "greens.txt"))}
            if skip_test_gate:
                env["FIXTURE_SKIP_TEST_GATE"] = "1"
            args = ["run", "--story", "STORY-1", "--from", "plan", "--tool", "stand-in", "--shared-builder"] \
                + (["--dry-run"] if dry else [])
            code, output = run_runner(runner, root, *args, env=env)
            journal = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "journal.tsv")
            starts = [l.split("\t")[2] for l in open(journal, encoding="utf-8").read().splitlines()
                      if "\tstage-start\t" in l] if os.path.isfile(journal) else []
            return code, output, starts, story_delivered(root)
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
    code, output, starts, delivered = shared_run(
        story=STORY.replace("status: approved\n", "status: approved\nkind: journey\n")
        .replace("depends_on: []", "depends_on: [STORY-0]"), green=both_green)
    stage_lines = [l.split("  (")[0][3:] for l in output.splitlines()
                   if l.startswith("── stage ") and "(skipped" not in l]
    check("shared builder: a journey shares plan and test, its test gate re-checked, and is delivered",
          code == 0 and stage_lines == ["stage plan+test", "stage judge", "stage document"] and delivered
          and "── gate test  (re-checked by the runner)" in output,
          f"exit {code}; {stage_lines}; {output.strip().splitlines()[-3:]}")
    code, output, starts, delivered = shared_run(story=ADOPTED, green=both_green)
    stage_lines = [l.split("  (")[0][3:] for l in output.splitlines()
                   if l.startswith("── stage ") and "(skipped" not in l]
    check("shared builder: an adopted story shares plan and test, then its judge and the adopt gate deliver it",
          code == 0 and stage_lines == ["stage plan+test", "stage judge"] and delivered,
          f"exit {code}; {stage_lines}; {output.strip().splitlines()[-3:]}")
    code, output, starts, delivered = shared_run(dry=True)
    check("shared builder: the dry run shows the one shared invocation and starts nothing",
          "stage plan+test+build+tidy  (tool: stand-in, one shared context)" in output and starts == [],
          [l for l in output.splitlines() if l.startswith("── stage")])

    # 1c. a stage that writes no file stops the run, and says which file was missing
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "true"})
        check("runner: a stage that produced no file stops the run",
              code != 0 and "produced no .dca-factory/runs/STORY-1/plan.md" in output,
              output.strip().splitlines()[-1] if output.strip() else "no output")

    # 1d. a stage that escalates stops the run
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        escalating = ('mkdir -p .dca-factory/runs/STORY-1; printf "## Context\\n## Changes\\n'
                      '## Acceptance criteria\\n## needs-human\\nSomeone must decide.\\n" '
                      '> .dca-factory/runs/STORY-1/plan.md')
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": escalating})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: a stage that ends with needs-human stops the run",
              code != 0 and stages == ["plan"] and "needs-human" in output,
              f"stages that ran: {stages}, exit {code}")

    # 1d1. a bare needs-human heading from the template is not an escalation
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        bare = ('mkdir -p .dca-factory/runs/STORY-1; printf "## Context\\n## Changes\\n'
                '## Acceptance criteria\\n## needs-human\\n(none)\\n" > .dca-factory/runs/STORY-1/plan.md')
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": bare})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: an empty needs-human heading does not stop the run",
              stages[:2] == ["plan", "test"] and "ends with a needs-human section" not in output,
              f"stages that ran: {stages}")
        bare = bare.replace("(none)", "None.")
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "plan", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": bare})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: a needs-human heading that says `None.` does not stop the run",
              stages[:2] == ["plan", "test"] and "ends with a needs-human section" not in output,
              f"stages that ran: {stages}")

    # 1d3. `run --story` without --from starts where the story's files say, never at plan by default
    def gated(root):
        copy_scripts(runner, root)
        return root

    with tmpdir() as root:
        gated(build_project(root, extra_sources=((".dca-factory/runs/STORY-1/plan.md", "# Plan\n"),)))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        order = [line.strip()[3:].split("  (")[0].strip() for line in output.splitlines() if line.startswith("── ")]
        check("runner: without --from a story with plan and tests written resumes at build, not at plan",
              code == 0 and order[:1] == ["stage build"] and "starts at build" in output, f"got {order}")
    with tmpdir() as root:
        gated(build_project(root, document="# Document\n", story=delivered_story(STORY)))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "false"})
        check("runner: a delivered story runs nothing without --from, and says so",
              code == 0 and "is delivered" in output and "── " not in output, output[-300:])
    with tmpdir() as root:
        gated(build_project(root, story=STORY.replace("depends_on: []", "depends_on: [STORY-0]")))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "false"})
        check("runner: a story whose dependency is not delivered does not run without --from, and names --from",
              code == 1 and "blocked" in output and "--from" in output and "── " not in output, output[-300:])
    # 1d3'. a --from that names no stage runs nothing and keeps the count
    with tmpdir() as root:
        gated(build_project(root, rounds=2))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "Build", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "echo INVOKED"})
        rounds = open(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".rounds"), encoding="utf-8").read().strip() \
            if os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".rounds")) else "gone"
        check("runner: an unknown --from stage is refused (exit 2), invokes nothing and keeps the rounds",
              code == 2 and "INVOKED" not in output and rounds == "2", f"exit {code}; rounds {rounds}")
    # 1d4. three rounds stop a story; a person's --from starts a new count, keeps the old one, and the gate
    #      checks the existing file before the stage is invoked
    with tmpdir() as root:
        gated(build_project(root, rounds=3, extra_sources=((".dca-factory/runs/STORY-1/plan.md", "# Plan\n"),
                                                          (".dca-factory/runs/STORY-1/.gate-test.txt", "gate:fail rounds — stale\n"))))
        stopped_code, stopped = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                           env={"FACTORY_TOOL_CMD": "false"})
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "test", "--tool", "stand-in",
                                  "--max-stages", "0", env={"FACTORY_TOOL_CMD": "false"})
        kept = glob.glob(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "rounds.*"))
        journal_path = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "journal.tsv")
        journal = open(journal_path, encoding="utf-8").read() if os.path.isfile(journal_path) else ""
        check("runner: a story stopped after three rounds does not run without --from",
              stopped_code == 1 and "stopped" in stopped and "── " not in stopped, stopped[-300:])
        check("runner: --from starts a new count of rounds and keeps the old one in the journal folder",
              not os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".rounds")) and len(kept) == 1
              and "\trounds-reset\t" in journal, output[-400:])
        check("runner: resumed at a gated stage whose file exists, the gate decides before the stage is invoked",
              "── gate test  (the file exists" in output
              and output.index("── gate test  (the file exists") < (output.find("── stage test") % (len(output) + 1)),
              output[-400:])
    # 1d5. a program missing on the PATH stops the story once, without a round
    with tmpdir() as root:
        gated(build_project(root, tests=None, profile=PROFILE.replace("compile: true", "compile: dca-no-such-tool"),
                            extra_sources=((".dca-factory/runs/STORY-1/plan.md", "# Plan\n"), ("tests.fixture", TESTS))))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--from", "test", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": "mkdir -p .dca-factory/runs/STORY-1; cp tests.fixture .dca-factory/runs/STORY-1/tests.md"})
        stages = [line.split()[2] for line in output.splitlines() if line.startswith("── stage ")]
        check("runner: a gate refused on the environment stops once, counts no round and runs no stage again",
              code == 1 and stages == ["test"] and "refused on the environment" in output
              and not os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".rounds")),
              f"stages {stages}, exit {code}: {output[-400:]}")

    # 1d2. a stage that asks writes the record; the run names it and how to resume
    with tmpdir() as root:
        build_project(root)
        copy_scripts(runner, root)
        asking = ('mkdir -p .dca-factory/runs/STORY-1 project/epics/sample/STORY-1.decisions; '
                  'cat "$FIXTURE_DECISION" > project/epics/sample/STORY-1.decisions/01.md; '
                  'cat "$FIXTURE_PLAN" > .dca-factory/runs/STORY-1/plan.md')
        with open(os.path.join(root, "decision.md"), "w", encoding="utf-8") as handle:
            handle.write(DECISION)
        with open(os.path.join(root, "plan.md"), "w", encoding="utf-8") as handle:
            handle.write(PLAN_ASKING)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "stand-in",
                                  env={"FACTORY_TOOL_CMD": asking,
                                       "FIXTURE_DECISION": shell_path(os.path.join(root, "decision.md")),
                                       "FIXTURE_PLAN": shell_path(os.path.join(root, "plan.md"))})
        check("runner: a stage that asks a question names the record and the command that resumes",
              code == 3 and "project/epics/sample/STORY-1.decisions/01.md" in output
              and "run --story STORY-1 — it resumes at plan" in output,
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
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        profile_text = open(os.path.join(root, "dca-factory.profile.yaml"), encoding="utf-8").read() \
            if os.path.isfile(os.path.join(root, "dca-factory.profile.yaml")) else ""
        check("install: a Playwright setup it finds becomes the end-user command and `browser: playwright`",
              "e2eTest: ./gradlew test-e2e --rerun" in profile_text and "\nbrowser: playwright" in profile_text,
              [l for l in profile_text.splitlines() if l.startswith(("e2eTest", "browser"))])
    # 1d'. the carriers a profile names reach Claude's own skill directory, and only those
    carrier = next((name for name in ("dca-modelling", "review-clean-code", "e2e-testing")
                    if any(os.path.isdir(os.path.join(plugins_dir, plugin, "skills", name))
                           for plugin in os.listdir(plugins_dir))), None) \
        if os.path.isdir(plugins_dir := os.path.dirname(os.path.dirname(source))) else None
    if carrier:
        with tmpdir() as root:
            build_project(root, profile=PROFILE + f"carrier.build: {carrier}\n")
            code, output = run_setup(runner, root, "--tool", "claude", "--from", source)
            skills_dir = os.path.join(root, ".claude", "skills")
            # skill folders only: a copying install (no symlinks, as on Windows) keeps its list beside them
            entries = sorted(e for e in os.listdir(skills_dir) if not e.startswith(".")) if os.path.isdir(skills_dir) else []
            check("install: a carrier the profile names is placed in .claude/skills beside the pipeline, "
                  "no other craft skill", os.path.isdir(skills_dir) and not os.path.islink(skills_dir)
                  and os.path.isfile(os.path.join(skills_dir, carrier, "SKILL.md"))
                  and "factory-run" in entries
                  and len(entries) == 1 + sum(os.path.isfile(os.path.join(source, d, "SKILL.md")) for d in os.listdir(source)),
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
        run_setup(runner, root, "--tool", "codex", "--from", source)
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
            run_setup(runner, root, "--tool", "codex", "--from", source)
            check("install: a link the *project* made is not replaced either",
                  os.path.realpath(os.path.join(skills, "stage-plan")) == os.path.realpath(elsewhere),
                  f"stage-plan now points at {os.path.realpath(os.path.join(skills, 'stage-plan'))}")
    else:
        print("  skip  install: the two link cases — this account cannot create symlinks, so install copies")

    # 1g. a backlog run: story after story, past a question, and back to it once it is answered.
    # The stand-in writes each stage's file; STORY-1's plan stage asks until its record is answered.
    stand_in_backlog = """#!/bin/sh
echo "$FACTORY_STORY $FACTORY_STAGE" >> invocations.log
d=".dca-factory/runs/$FACTORY_STORY"; rec=project/epics/sample/STORY-1.decisions/01.md
mkdir -p "$d" project/epics/sample/STORY-1.decisions
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
        copy_scripts(runner, root)
        return {"FACTORY_TOOL_CMD": "sh stand-in.sh"}

    def invocations(root):
        path = os.path.join(root, "invocations.log")
        return open(path, encoding="utf-8").read().split("\n")[:-1] if os.path.isfile(path) else []

    def answer(root):
        with open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"), "a",
                  encoding="utf-8") as handle:
            handle.write(ANSWER)

    # WP-66: a story that waits for acceptance stops the runner like a question, and counts no round
    with tmpdir() as root:
        env = backlog_fixture(root)
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as h:
            h.write("acceptance: all\n")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", env=env)
        folder = os.path.join(root, ".dca-factory", "runs", "STORY-2")
        check("acceptance: the runner stops with exit 3 at the document gate's question, counting no round",
              code == 3 and not story_delivered(root, "STORY-2")
              and os.path.isfile(os.path.join(root, "project", "epics", "sample", "STORY-2.decisions", "accept-1.md"))
              and not os.path.isfile(os.path.join(folder, ".gate-document.txt"))
              and not os.path.isfile(os.path.join(folder, ".rounds")),
              f"exit {code}; {output.strip().splitlines()[-2:]}")
        with open(os.path.join(root, "project", "epics", "sample", "STORY-2.decisions", "accept-1.md"), "a",
                  encoding="utf-8") as h:
            h.write("\n## Answer\nanswer: accepted\nby: a-human\nat: 2026-09-25T15:00:00Z\n")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", env=env)
        check("acceptance: once accepted, the runner's next run delivers the story",
              code == 0 and story_delivered(root, "STORY-2"),
              f"exit {code}; {output.strip().splitlines()[-2:]}")

    six = ["plan", "test", "build", "tidy", "judge", "document"]
    with tmpdir() as root:
        env = backlog_fixture(root)
        code, output = run_runner(runner, root, "run", env=env)
        ran = invocations(root)
        check("backlog: a story that asks at its plan stage does not stop the stories that do not need it",
              code == 0 and ran == ["STORY-1 plan"] + [f"STORY-2 {s}" for s in six],
              f"exit {code}, invocations {ran}, last lines: {output.strip().splitlines()[-3:]}")
        check("backlog: the story that depends on the waiting one stays blocked",
              "STORY-3  blocked" in output, [l for l in output.splitlines() if "STORY-3" in l])
        answer(root)
        code, output = run_runner(runner, root, "run", env=env)
        ran = invocations(root)[7:]
        check("backlog: after the answer the story resumes at the stage that asked, then its dependant runs",
              code == 0 and ran == [f"STORY-1 {s}" for s in six] + [f"STORY-3 {s}" for s in six],
              f"exit {code}, invocations {ran}, last lines: {output.strip().splitlines()[-4:]}")
        record = open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"),
                      encoding="utf-8").read()
        check("backlog: the resumed stage's answer is stamped applied", "## Applied" in record)
        code, output = run_runner(runner, root, "run", env=env)
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
            process = subprocess.Popen([BASH, runner, "run", "--watch", "--interval", "1"],
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
        code, output = run_runner(runner, root, "run", "--max-stages", "2", env=env)
        check("backlog: --max-stages stops before the next invocation and keeps what ran",
              code == 4 and invocations(root) == ["STORY-1 plan", "STORY-2 plan"]
              and os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-2", "plan.md")),
              f"exit {code}, invocations {invocations(root)}")
    with tmpdir() as root:
        env = backlog_fixture(root)
        os.makedirs(os.path.join(root, ".dca-factory"), exist_ok=True)
        open(os.path.join(root, ".dca-factory", "stop"), "w").close()
        code, output = run_runner(runner, root, "run", env=env)
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
              and open(os.path.join(root, ".dca-factory", "runs", "STORY-2", ".rounds"), encoding="utf-8").read().strip() == "1",
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
            "  judge) mkdir -p project/epics/sample/STORY-2.decisions; cat fixture/conflict.md > project/epics/sample/STORY-2.decisions/01.md; "
            "cat fixture/judge-conflict.md > \"$d/judge.md\" ;;")
        with open(os.path.join(root, "stand-in.sh"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(stand_in)
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        check("runner: a judge's story conflict with a record waits for the answer at the stage that applies it",
              code == 3 and "it resumes at test" in output, f"exit {code}; {[l for l in output.splitlines() if 'decision' in l][:3]}")

    # 1n. what a stage cost: recorded per invocation, summed per story and stage, bounded per story
    claude_like = ('{"result":"done","total_cost_usd":0.01,"modelUsage":{"some-model":{"inputTokens":100,'
                   '"outputTokens":900,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}}')
    with tmpdir() as root:
        env = backlog_fixture(root)
        env.update({"FIXTURE_USAGE": claude_like, "FACTORY_USAGE_FORMAT": "claude-json"})
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        journal = open(os.path.join(root, ".dca-factory", "runs", "STORY-2", ".verify", "journal.tsv"), encoding="utf-8").read()
        stages = usage_json(os.path.join(root, ".agents", "factory", "story-gate.py"), root, "STORY-2")
        check("usage: each invocation's tokens land in the story's journal",
              code == 0 and journal.count("\tusage\t") == 6 and "output=900" in journal,
              f"exit {code}; usage lines {journal.count(chr(9) + 'usage' + chr(9))}")
        check("usage: the report sums tokens and cost per stage and per story",
              len(stages) == 6 and sum(e["tokens"] for e in stages.values()) == 6000
              and round(sum(e["cost"] for e in stages.values()), 2) == 0.06
              and sum(e["output"] for e in stages.values()) == 5400,
              {k: (e["tokens"], e["output"], e["cost"]) for k, e in stages.items()})
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
        stages = usage_json(os.path.join(root, ".agents", "factory", "story-gate.py"), root, "STORY-2")
        check("usage: a tool that reports nothing is counted as unknown, never as zero",
              sum(e["runs"] - e["measured"] for e in stages.values()) == 6
              and all(e["tokens"] == 0 for e in stages.values()), {k: (e["runs"], e["measured"]) for k, e in stages.items()})

    # 1l. a resumed document stage whose file already holds is not invoked again
    with tmpdir() as root:
        env = backlog_fixture(root)
        run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in", env=env)
        undeliver(root, "STORY-2")
        before = len(invocations(root))
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  "--from", "document", env=env)
        check("runner: a document file that already holds costs no invocation on resume",
              code == 0 and len(invocations(root)) == before and "already holds" in output
              and story_delivered(root, "STORY-2"),
              f"exit {code}, {len(invocations(root)) - before} new invocation(s)")

    # 1o. update: the newest pipeline, the same tools, links stay links and copies stay copies
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "codex", "--from", source)
        stamp = os.path.join(root, ".agents", "factory", "gate.installed")
        text = open(stamp, encoding="utf-8").read()
        with open(stamp, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"version: .*", "version: 0.0.1", text))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
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
              and "contract: 1" in open(os.path.join(root, "dca-factory.profile.yaml"), encoding="utf-8").read(),
              [l for l in output.splitlines() if "contract" in l][:2])
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
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
        run_setup(runner, root, "--tool", "codex", "--from", source)
        stamp = os.path.join(root, ".agents", "factory", "gate.installed")
        text = open(stamp, encoding="utf-8").read()
        with open(stamp, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"version: .*", "version: 0.0.1", text))
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "status", "--live",
                                  env={"FACTORY_PLUGIN_DIR": source})
        check("status --live: a project behind the pipeline is told so, with the update to run",
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
            '  check_dca_setup "$from"\n', '  check_dca_setup "$from"\n  : > .agents/factory/added-by-the-newer-install\n', 1)
        with open(newer_runner, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        project = os.path.join(root, "project")
        os.makedirs(project)
        build_project(project)
        run_setup(runner, project, "--tool", "claude", "--from", source, "--copy")
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
        code, output = run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        manifest = open(os.path.join(skills_dir, ".dca-factory-skills"), encoding="utf-8").read().split()
        check("copies: the project's own skills stay, a same-named one is not overwritten, and the list names only "
              "what the pipeline copied",
              "OURS" in open(os.path.join(skills_dir, "stage-plan", "SKILL.md"), encoding="utf-8").read()
              and os.path.isdir(os.path.join(skills_dir, "our-own-skill")) and "factory-run" in manifest
              and "stage-plan" not in manifest and "our-own-skill" not in manifest
              and "kept the project's own .claude/skills/stage-plan" in output, output.strip().splitlines()[-3:])
        dropped = os.path.join(tempfile.mkdtemp(), "trimmed-plugin")   # outside the project: an update's source never lies inside it
        shutil.copytree(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")), dropped, symlinks=True)
        shutil.rmtree(os.path.join(dropped, "factory-decisions"))
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "update",
                                  "--from", shell_path(dropped))
        check("copies: a skill the pipeline dropped is removed on update; the project's own stay",
              code == 0 and not os.path.exists(os.path.join(skills_dir, "factory-decisions"))
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
              and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "STORY-2", "plan.md")),
              f"exit {result.returncode}; {result.stderr.strip().splitlines()[-1:] if result.stderr else ''}")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "stand-in",
                                  env=dict(env, CLAUDE_CODE_SESSION_ID="some-session"))
        check("runner: a stand-in starts no tool and is not refused inside a session",
              code == 0 and len(invocations(root)) == 6, f"exit {code}")

    # 1q. a custom command is handed the stage's model and the journal says it was not applied by the runner
    with tmpdir() as root:
        env = backlog_fixture(root)
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("model.claude.build: model-q\n")
        env = dict(env, FACTORY_TOOL_CMD='echo "$FACTORY_STAGE=$FACTORY_MODEL" >> models.log; sh stand-in.sh')
        with open(os.path.join(root, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("models.log\n")
        code, output = run_runner(runner, root, "run", "--story", "STORY-2", "--tool", "claude", env=env)
        seen = open(os.path.join(root, "models.log"), encoding="utf-8").read().split() \
            if os.path.isfile(os.path.join(root, "models.log")) else []
        journal = open(os.path.join(root, ".dca-factory", "runs", "STORY-2", ".verify", "journal.tsv"), encoding="utf-8").read() \
            if os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-2", ".verify", "journal.tsv")) else ""
        status = subprocess.run([sys.executable, cli_in(root), "--status",
                                 "--story", "STORY-2"], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout
        build_row = next((l for l in status.splitlines() if "Stages" in l), "")
        check("model: a custom command gets FACTORY_MODEL for its stage only, the journal records the request "
              "as not applied by the runner, and the status says so",
              "build=model-q" in seen and "plan=" in seen
              and "model_requested=model-q\tmodel_applied=no (passed as FACTORY_MODEL" in journal
              and "requested model-q: not applied" in build_row,
              f"exit {code}; {seen}; {build_row}")

    # 1p. a runner does not start while another worker holds the checkout
    with tmpdir() as root:
        env = backlog_fixture(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run([sys.executable, cli_in(root), "--claim",
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
        run_setup(runner, root, "--tool", "claude", "--from", source)
        run_runner(runner, root, "update", "--from", source)
        agents = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
        settings = json.load(open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8"))
        commands = [h["command"] for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]
        check("priming: AGENTS.md carries the pipeline's section once, and keeps the project's own lines",
              agents.count("<!-- dca-factory: start -->") == 1 and "The project's own line." in agents
              and "factory-cli.py --status --brief" in agents and "story-gate.py --status" not in agents
              and "factory.sh status" not in agents, agents[-300:])
        check("priming: the section asks once, in fixed words, whether a user story goes through the factory",
              '"As a story through the factory — to an existing epic, a new epic — or directly by hand?"' in agents
              and "`/factory-run` with the person's words" in agents, agents[-900:])
        check("priming: Claude's SessionStart hook is added once, beside the project's own hooks",
              sum(1 for c in commands if c.endswith(".agents/factory/factory-cli.py --status --brief --session-start")) == 1
              and not any("story-gate.py --status" in c for c in commands)
              and "echo mine" in commands and not any("factory.sh" in c for c in commands), commands)
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "status", "--brief")
        lines = [l for l in output.splitlines() if l.startswith("factory: ") and "detection finds" not in l]
        check("priming: `factory.sh status --brief` prints the state and what comes next, then what is missing",
              code == 0 and len(lines) >= 2 and "next:" in lines[1]
              and all("/factory-setup" in l for l in lines[2:]), lines)
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
                   env={"FACTORY_TOOL_CMD": 'mkdir -p .dca-factory/runs/STORY-1; printf "## Verdict\\nverdict: pass\\n" '
                                            '> .dca-factory/runs/STORY-1/judge.md'})
        snap = read_snapshot(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "tree-before-judge.txt"))
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
                 "FACTORY_TOOL_CMD": 'mkdir -p .dca-factory/runs/STORY-1; printf "## Verdict\\nverdict: pass\\n" '
                                     '> .dca-factory/runs/STORY-1/judge.md'})
        tree = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "tree-before-judge.txt")
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
        shutil.rmtree(os.path.join(root, ".agents"), ignore_errors=True)
        with open(os.path.join(root, ".agents"), "w", encoding="utf-8") as handle:
            handle.write("not a directory\n")
        code, output = run_setup(runner, root, "--tool", "codex", "--from", source)
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
        code, output = run_setup(runner, root, "--tool", "codex", "--from", source)
        check("install: an architecture test nested in a source set is found",
              "architecture governance found" in output,
              [l for l in output.splitlines() if "governance" in l])

    # 1j. the install stamps where the gate came from, and a later run says when the project is
    # behind the pipeline. The gate itself cannot tell: a copied script has nothing to compare to.
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "codex", "--from", source)
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
        shutil.copy(os.path.join(os.path.dirname(runner), "factory-cli.py"), os.path.join(plugin, "factory-cli.py"))
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
        contract = re.search(r"^CONTRACT = (\d+)", body, re.M).group(1)
        with open(os.path.join(plugin, "story-gate.py"), "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^CONTRACT = \d+", f"CONTRACT = {int(contract) + 1}", body, count=1, flags=re.M))
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude",
                                  "--dry-run", env=env)
        check("install: a differing file contract is reported as a compatibility question",
              f"installed against file contract {contract}" in output and f"implements {int(contract) + 1}" in output
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
            os.makedirs(os.path.join(root, ".dca-factory", "runs", "STORY-1"))
            with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", "judge.md"), "w", encoding="utf-8") as handle:
                handle.write(f"# Judge\n\n## Verdict\nverdict: {verdict}\n")
            code, output = run_runner(
                runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                env={"FACTORY_VERIFY_VERDICT": "1"})
            # the dry run does not reach the judge, so read the parser directly
            # the function asks the cli beside the runner, so the sourced snippet gets what the runner defines
            parsed = subprocess.run(
                [BASH, "-c",
                 f'PY="{shell_path(sys.executable)}"; CLI="{shell_path(cli_of(runner))}"; cli() {{ "$PY" "$CLI" "$@"; }}; '
                 f'RUNS=.dca-factory/runs; sed -n "/^verdict_of/,/^}}/p" "{shell_path(runner)}" > fn.sh; '
                 f'. ./fn.sh; verdict_of STORY-1'],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
            check(f"runner: reads the verdict '{verdict}' from the file", parsed == expect,
                  f"parsed {parsed!r}")

    # 4. the round counter is a file, and it counts up
    with tmpdir() as root:
        os.makedirs(os.path.join(root, ".dca-factory", "runs", "STORY-1"))
        counted = subprocess.run(
            [BASH, "-c",
             f'RUNS=.dca-factory/runs; sed -n "/^bump_rounds/,/^}}/p" "{shell_path(runner)}" > fn.sh; '
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
                name = "dca-modelling" if plugin == "dca-core" else "stage-plan"
                write_file(folder, f"skills/{name}/SKILL.md",
                           f"---\nname: {name}\ndescription: {plugin} {version}\n---\n")
        return os.path.join(cache, "dca-factory", "0.2.0", "skills")
    if SYMLINKS:
        with tmpdir() as root, tmpdir() as home:
            build_project(root, profile=PROFILE + "carrier.build: dca-modelling\n")
            cached = cache_fixture(home)
            run_setup(runner, root, "--tool", "codex", "--from", shell_path(cached), "--link", env={"HOME": home})
            skills = os.path.join(root, ".codex", "skills")
            targets = {e: os.path.realpath(os.path.join(skills, e)) for e in os.listdir(skills)} \
                if os.path.isdir(skills) else {}
            check("install: from a plugin cache the neighbours' newest versions are linked, never an older "
                  "version of the pipeline itself",
                  targets.get("dca-modelling", "").endswith(os.path.join("dca-core", "0.2.0", "skills", "dca-modelling"))
                  and not any(os.sep + "0.1.0" + os.sep in t for t in targets.values()),
                  {k: v[-40:] for k, v in targets.items() if "0.1.0" in v or k == "dca-modelling"})
    with tmpdir() as root, tmpdir() as home:
        build_project(root, profile=PROFILE + "carrier.build: dca-modelling\n")
        cached = cache_fixture(home)
        run_setup(runner, root, "--tool", "claude", "--from", shell_path(cached), "--copy", env={"HOME": home})
        shutil.rmtree(os.path.join(home, ".claude", "plugins", "cache", "m", "dca-core"))
        code, output = run_runner(os.path.join(root, ".agents", "factory", "factory.sh"), root, "update",
                                  "--from", shell_path(cached), env={"HOME": home})
        carrier_copy = os.path.join(root, ".claude", "skills", "dca-modelling", "SKILL.md")
        manifest = os.path.join(root, ".claude", "skills", ".dca-factory-skills")
        check("copies: a copied carrier survives an update, also when no neighbour has it any more",
              code == 0 and os.path.isfile(carrier_copy)
              and "dca-modelling" in open(manifest, encoding="utf-8").read().split(), output.strip().splitlines()[-4:])
    with tmpdir() as root:
        build_project(root)
        shells = [b for b in ("/bin/bash",) if os.path.isfile(b)] or [BASH]
        in_git(root)
        completed = subprocess.run([shells[0], runner, "setup", "--tool", "none"], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        check("setup: `--tool none` writes gate, runner and hook — also under the system bash",
              completed.returncode == 0 and os.path.isfile(os.path.join(root, ".agents", "factory", "story-gate.py")),
              f"{shells[0]}: exit {completed.returncode}; {(completed.stderr or completed.stdout).strip()[-200:]}")
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "core.hooksPath", ".husky"], cwd=root, capture_output=True)
        with open(os.path.join(root, ".gitattributes"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("*.png binary")                          # no newline at the end
        code, output = run_setup(runner, root, "--tool", "claude")
        hooks = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=root, capture_output=True,
                               text=True).stdout.strip()
        attributes = open(os.path.join(root, ".gitattributes"), encoding="utf-8").read().splitlines()
        check("install: another hook manager's `core.hooksPath` is kept, and the install says how to chain",
              hooks == ".husky" and "left as it is" in output, f"hooksPath {hooks!r}")
        check("install: `.gitattributes` without a final newline keeps its last line whole",
              attributes[:1] == ["*.png binary"] and any(l.startswith(".dca-factory/runs/**") for l in attributes), attributes)
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
                                       env=dict(os.environ, FACTORY_TOOL_CMD="sleep 6"),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # Wait for the stage itself to be under way — the claim taken and the stage's start in the
            # journal — rather than for a fixed time a loaded machine does not keep.
            journal = os.path.join(root, ".dca-factory", "runs", "STORY-2", ".verify", "journal.tsv")
            deadline = time.time() + 20
            while time.time() < deadline and not (
                    os.path.exists(lock) and os.path.isfile(journal)
                    and "stage-start" in open(journal, encoding="utf-8", errors="replace").read()):
                time.sleep(0.1)
            time.sleep(0.3)
            process.terminate()
            time.sleep(0.8)
            held_while_running = os.path.exists(lock)
            process.communicate(timeout=30)
            check("runner: a TERM while a stage runs gives the checkout back only after that stage has ended",
                  held_while_running and not os.path.exists(lock) and process.returncode == 143,
                  f"held while running {held_while_running}, released {not os.path.exists(lock)}, "
                  f"exit {process.returncode}")

    # 5. install leaves live links from a checkout, one per skill, never the whole folder
    source = shell_path(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")))
    with tmpdir() as root:
        build_project(root)
        code, output = run_setup(runner, root, "--tool", "claude", "--from", source)
        target = os.path.join(root, ".claude", "skills")
        if SYMLINKS:
            link = os.path.join(target, "factory-run")
            check("install: from a checkout the pipeline's skills are live links for Claude Code, one per skill",
                  os.path.isdir(target) and not os.path.islink(target) and os.path.islink(link)
                  and os.path.realpath(link) == os.path.realpath(os.path.join(source, "factory-run")),
                  f"{target} → {os.path.realpath(link) if os.path.exists(link) else 'missing'}")
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
              status_code == 0 and "Waiting for you" in status_out and "Backlog" in status_out,
              f"exit {status_code}; {status_out[:120]}")
        usage_code, usage_out = run_runner(project_runner, root, "status", "--usage") if os.path.isfile(project_runner) \
            else (None, "")
        check("install: `factory.sh status --usage` passes on to the gate", usage_code == 0 and "Tokens" in usage_out,
              f"exit {usage_code}; {usage_out[:120]}")
        check("install: a stack profile is written when the project has none",
              os.path.isfile(os.path.join(root, "dca-factory.profile.yaml")))
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "codex", "--from", source)
        entries = os.listdir(os.path.join(root, ".codex", "skills"))
        pipeline = {"factory-run", "stage-plan", "stage-test", "stage-build", "stage-tidy",
                    "stage-judge", "stage-document", "factory-backlog", "factory-setup",
                    "factory-decisions", "factory-status", "factory-update", "factory-help"}
        check("install: a tool without plugins also gets the craft the profile may name",
              pipeline.issubset(set(entries)) and len(entries) > len(pipeline),
              f"{len(entries)} skills: {sorted(entries)[:6]}…")
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        target = os.path.join(root, ".claude", "skills", "factory-run")
        check("install --copy: a real copy for a project with no source to point at",
              os.path.isdir(target) and not os.path.islink(target))

    failed = [name for name, ok, _ in results if not ok]
    print(f"\nverify: {len(results) - len(failed)}/{len(results)} runner cases behaved as specified")
    return failed

# --- setup: the presets, the check and the write ------------------------------------------------
# What a build tool looks like is data (templates/presets/). These cases hold the profile the
# presets write to what the installer wrote before they existed — byte for byte in every active
# line — and the one change made on purpose: Gradle's test commands (`test:`, `e2eTest:`) carry
# `--rerun`, because an up-to-date task writes no new report and a required suite would prove nothing.

PRESET_FIXTURES = {
    "gradle": {"gradlew": "#!/bin/sh\n", "build.gradle": "plugins { id 'java' }\n"},
    "gradle-playwright": {"build.gradle.kts":
                          'dependencies { testImplementation("com.microsoft.playwright:playwright:1.62.0") }\n'},
    "gradle-playwright-e2e": {"build.gradle": "plugins { id 'java' }\napply from: \"gradle/plugins/test-e2e.gradle\"\n",
                              "gradle/plugins/test-e2e.gradle":
                                  "tasks.register('test-e2e', Test)\n"
                                  "dependencies { testE2eImplementation 'com.microsoft.playwright:playwright:1.62.0' }\n"},
    "gradle-conventions": {"gradlew": "#!/bin/sh\n",
                           ".agents/dca/conventions.md": "Run `./gradlew archTest` for the architecture rules.\n"},
    "gradle-integration": {"gradlew": "#!/bin/sh\n", "build.gradle": "apply from: 'gradle/plugins/test-integration.gradle'\n",
                           "gradle/plugins/test-integration.gradle": "tasks.register('test-integration', Test)\n"},
    "maven": {"pom.xml": "<project/>\n"},
    "maven-integration": {"pom.xml": "<project><source>src/test-integration/java</source></project>\n"},
    "dotnet-integration": {"App.sln": "\n", "tests/App.IntegrationTests/App.IntegrationTests.csproj": "<Project/>\n"},
    "maven-playwright": {"pom.xml": "<project><dependency>com.microsoft.playwright</dependency></project>\n"},
    "dotnet": {"App.sln": "\n"},
    "dotnet-playwright": {"App.sln": "\n", "tests/App.E2E/App.E2E.csproj":
                          '<Project><PackageReference Include="Microsoft.Playwright" /></Project>\n'},
    "pytest-ini": {"pytest.ini": "[pytest]\n"},
    "pytest-pyproject": {"pyproject.toml": "[tool.pytest.ini_options]\n"},
    "pytest-setupcfg": {"setup.cfg": "[pytest]\n"},
    "npm-playwright": {"package.json": '{"devDependencies": {"@playwright/test": "1.62.0"}}\n'},
    "empty": {},
}
_GRADLE = ['compile: ./gradlew testClasses', 'test: ./gradlew test --rerun', 'e2eTest: ./gradlew test --rerun',
           'filterFlag: --tests', 'filterFormat: "{class}.{method}"', 'architecture: ./gradlew test-architecture']
_MAVEN = ['compile: ./mvnw test-compile', 'test: ./mvnw test', 'e2eTest: ./mvnw test', 'filterFlag: -Dtest',
          'filterFormat: "{class}#{method}"', 'architecture: ./mvnw -Dtest=*ArchitectureTest test']
_DOTNET = ['compile: dotnet build', 'test: dotnet test --logger trx', 'e2eTest: dotnet test --logger trx',
           'filterFlag: --filter', 'filterFormat: "FullyQualifiedName~{class}.{method}"',
           'architecture: dotnet test --filter FullyQualifiedName~Architecture', 'covers.test: **']
_PYTEST = ['test: {py} -m pytest -q --junitxml=test-results/pytest.xml',
           'e2eTest: {py} -m pytest -q --junitxml=test-results/pytest.xml', 'filterFormat: "{file}::{method}"',
           'covers.test: **']
PRESET_GOLDEN = {
    "gradle": _GRADLE,
    "gradle-playwright": _GRADLE + ["browser: playwright"],
    "gradle-playwright-e2e": [_GRADLE[0] + " testE2eClasses", _GRADLE[1], "e2eTest: ./gradlew test-e2e --rerun"]
                             + _GRADLE[3:] + ["browser: playwright"],
    "gradle-conventions": _GRADLE[:5] + ["architecture: ./gradlew archTest"],
    "gradle-integration": _GRADLE + ["test.integration: ./gradlew test-integration --rerun"],
    "maven": _MAVEN,
    "maven-integration": _MAVEN + ["test.integration: ./mvnw test", "covers.test.integration: src/test-integration/"],
    "dotnet-integration": _DOTNET + ["test.integration: dotnet test tests/App.IntegrationTests --logger trx"],
    "maven-playwright": _MAVEN + ["browser: playwright"],
    "dotnet": _DOTNET,
    "dotnet-playwright": _DOTNET[:2] + ["e2eTest: dotnet test tests/App.E2E/App.E2E.csproj --logger trx"]
                         + _DOTNET[3:] + ["browser: playwright"],
    "pytest-ini": _PYTEST, "pytest-pyproject": _PYTEST, "pytest-setupcfg": _PYTEST,
    "npm-playwright": ["browser: playwright"],
    "empty": [],
}


def active_lines(path):
    if not os.path.isfile(path):
        return None
    return [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip() and not l.startswith("#")]


def tree_digest(root):
    """Every file's content under root, for "changed no file" — the tool folders' links included."""
    seen = {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            path = os.path.join(folder, name)
            try:
                seen[os.path.relpath(path, root)] = hashlib.sha256(open(path, "rb").read()).hexdigest() \
                    if not os.path.islink(path) else "link:" + os.readlink(path)
            except OSError:
                seen[os.path.relpath(path, root)] = "?"
    return seen


def verify_setup(runner, verbose=False):
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
        if not ok and detail:
            print(f"          {detail}")

    source = shell_path(os.path.normpath(os.path.join(os.path.dirname(runner), "..", "..")))
    profile_of = lambda root: os.path.join(root, "dca-factory.profile.yaml")
    project_runner = lambda root: os.path.join(root, ".agents", "factory", "factory.sh")

    def fixture(root, files):
        for path, text in files.items():
            write_file(root, path, text)

    # the pipeline alone, with no method plugin beside it: what the presets write, no carrier line
    lone_home = tempfile.mkdtemp()
    lone = shell_path(os.path.join(lone_home, "plugins", "dca-factory", "skills"))
    shutil.copytree(source, lone, symlinks=True)

    # item 2: the golden profiles, before and after the presets
    python = None
    for name, files in PRESET_FIXTURES.items():
        with tmpdir() as root:
            fixture(root, files)
            code, output = run_setup(runner, root, "--tool", "none", "--from", lone)
            lines = active_lines(profile_of(root)) or []
            if python is None:
                python = next((l.split()[1] for l in lines if l.startswith("test:") and "pytest" in l), None)
            wanted = ["contract: " + re.search(r"^contract: (\d+)", open(os.path.join(
                source, "factory-run", "templates", "factory.profile.yaml.tmpl"), encoding="utf-8").read(), re.M).group(1)]
            wanted += [l.replace("{py}", python or "python3") for l in PRESET_GOLDEN[name]]
            check(f"presets: the {name} fixture gets the profile the installer wrote before the presets",
                  code == 0 and lines == wanted, f"exit {code}; got {lines}; want {wanted}")

    # a profile without an integration level is named until someone decides one
    for name, want in (("gradle", True), ("gradle-integration", False)):
        with tmpdir() as root:
            fixture(root, PRESET_FIXTURES[name])
            run_setup(runner, root, "--tool", "none", "--from", lone)
            checked = run_setup(runner, root, "--check")[1]
            check(f"setup: --check {'names' if want else 'does not name'} a missing integration level ({name})",
                  ("no integration level" in checked or "? integration level" in checked) == want, checked.strip()[-400:])

    # item 4: a new stack is one file — a made-up one in FACTORY_STACKS_DIR, no change to the script
    with tmpdir() as root, tmpdir() as stacks:
        write_file(stacks, "cargo.preset", "kind: stack\norder: 10\ndetect.exists: Cargo.toml\n"
                                            "compile: cargo test --no-run\ntest: cargo nextest run\n")
        write_file(root, "Cargo.toml", "[package]\n")
        code, output = run_setup(runner, root, "--tool", "none", "--from", lone, env={"FACTORY_STACKS_DIR": stacks})
        lines = active_lines(profile_of(root)) or []
        check("presets: a preset file in FACTORY_STACKS_DIR makes a profile for a stack the script never names",
              code == 0 and "compile: cargo test --no-run" in lines and "test: cargo nextest run" in lines, lines)
    body = open(runner, encoding="utf-8").read().splitlines()
    knowledge = [f"{n}: {l.strip()}" for n, l in enumerate(body, 1)
                 if re.search(r"gradlew|mvnw|dotnet|pytest|playwright", l, re.I) and not l.strip().startswith("#")]
    check("presets: the runner carries no stack knowledge outside comments", not knowledge, knowledge[:3])

    # item 9: no repository, no setup — and nothing written
    with tmpdir() as root:
        write_file(root, "build.gradle", "plugins { id 'java' }\n")
        code, output = run_runner(runner, root, "setup", "--tool", "none", "--from", source)
        check("setup: outside a git repository it stops with one line and writes nothing",
              code == 1 and "not a git repository" in output and not os.path.exists(os.path.join(root, ".agents")),
              f"exit {code}; {output.strip()}")

    # item 10: the check and the write, on an empty, a complete and a conflicting profile
    with tmpdir() as root:
        fixture(root, PRESET_FIXTURES["gradle-playwright-e2e"])
        in_git(root)
        code, output = run_runner(runner, root, "setup", "--check")
        check("setup --check: without a runner it writes nothing and exits 1",
              code == 1 and "no runner — factory.sh setup" in output and not os.path.exists(os.path.join(root, ".agents")),
              f"exit {code}; {output.strip()}")
        run_setup(runner, root, "--tool", "none", "--from", source)
        code, output = run_runner(runner, root, "setup", "--check")
        check("setup --check: right after setup the profile declares everything detection finds",
              code == 0 and "declares everything" in output, output.strip().splitlines()[-2:])
        before = tree_digest(root)
        code, output = run_runner(runner, root, "setup")
        check("setup: a second bare setup on an installed project reports and changes no file",
              code == 0 and "installs nothing" in output and tree_digest(root) == before,
              f"exit {code}; {output.strip().splitlines()[:1]}")
        profile = profile_of(root)
        text = open(profile, encoding="utf-8").read()
        with open(profile, "w", encoding="utf-8") as handle:
            handle.write(text.replace("browser: playwright\n", "").replace("\ntest: ./gradlew test --rerun", "\ntest: ./gradlew test"))
        code, output = run_runner(runner, root, "setup", "--check")
        check("setup --check: a missing detected key exits 1 and names the check it switches on",
              code == 1 and "? browser   missing" in output and "playwright" in output and "the plan takes browser tests" in output,
              output.strip().splitlines())
        check("setup --check: a value that differs is a note — kept, with the key --replace takes",
              "· test   differs" in output and "--replace test" in output, [l for l in output.splitlines() if "differs" in l])
        before = tree_digest(root)
        run_runner(runner, root, "setup", "--check")
        check("setup --check: read-only", tree_digest(root) == before)
        code, output = run_runner(runner, root, "setup", "--write")
        after = open(profile, encoding="utf-8").read()
        check("setup --write: adds the missing key and keeps the person's value",
              code == 0 and "\nbrowser: playwright" in after and "test: ./gradlew test\n" in after, output.strip())
        once = tree_digest(root)
        code, output = run_runner(runner, root, "setup", "--write")
        check("setup --write: a second write changes nothing", code == 0 and tree_digest(root) == once
              and "nothing written" in output, output.strip())
        code, output = run_runner(runner, root, "setup", "--write", "--replace", "test")
        check("setup --write --replace: takes the detected value for that one key",
              code == 0 and "\ntest: ./gradlew test --rerun" in open(profile, encoding="utf-8").read(), output.strip())
        code, output = run_runner(runner, root, "setup", "--check")
        check("setup --check: the conflict resolved, exit 0", code == 0, output.strip().splitlines()[-1:])

    # formatFix beside every detected format; covers.* only while its command is the detected one
    with tmpdir() as root:
        fixture(root, {"build.gradle": "plugins { id 'com.diffplug.spotless' version '8.2.1' }\n"})
        run_setup(runner, root, "--tool", "none", "--from", source)
        lines = active_lines(profile_of(root)) or []
        check("presets: a detected formatter writes its check and its fix together",
              "format: ./gradlew spotlessCheck" in lines and "formatFix: ./gradlew spotlessApply" in lines, lines)
    with tmpdir() as root:
        fixture(root, {"App.sln": "\n", ".editorconfig": "root = true\n"})
        run_setup(runner, root, "--tool", "none", "--from", source)
        lines = active_lines(profile_of(root)) or []
        check("presets: dotnet format is detected by .editorconfig beside a solution, with its fix",
              "format: dotnet format --verify-no-changes" in lines and "formatFix: dotnet format" in lines, lines)
        text = open(profile_of(root), encoding="utf-8").read()
        with open(profile_of(root), "w", encoding="utf-8") as handle:
            handle.write(text.replace("test: dotnet test --logger trx", "test: dotnet test tests/Unit --logger trx")
                         .replace("covers.test: **\n", ""))
        code, output = run_runner(runner, root, "setup", "--check")
        check("setup --check: `covers.test` is not proposed to a `test:` the person narrowed",
              code == 0 and "covers.test" not in output and "· test   differs" in output, output.strip().splitlines())
    with tmpdir() as root:
        write_file(root, ".editorconfig", "root = true\n")
        write_file(root, "build.gradle", "plugins { id 'java' }\n")
        run_setup(runner, root, "--tool", "none", "--from", source)
        check("presets: .editorconfig alone makes no .NET formatter of a Gradle project",
              not any(l.startswith("format") for l in active_lines(profile_of(root)) or []))

    # item 7: the profile is written before the skills, so a carrier it names is linked in the same run
    carrier = next((name for name in ("dca-modelling", "e2e-testing")
                    if any(os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(source)), plugin, "skills", name))
                           for plugin in os.listdir(os.path.dirname(os.path.dirname(source))))), None)
    if carrier and SYMLINKS:
        with tmpdir() as root, tmpdir() as plugins:
            # the pipeline copied beside the real method plugins, its template naming the carrier
            real = os.path.dirname(os.path.dirname(source))
            for plugin in os.listdir(real):
                if plugin != "dca-factory" and os.path.isdir(os.path.join(real, plugin, "skills")):
                    os.makedirs(os.path.join(plugins, plugin))
                    os.symlink(os.path.join(real, plugin, "skills"), os.path.join(plugins, plugin, "skills"))
            copy = os.path.join(plugins, "dca-factory", "skills")
            shutil.copytree(source, copy, symlinks=True)
            with open(os.path.join(copy, "factory-run", "templates", "factory.profile.yaml.tmpl"), "a",
                      encoding="utf-8") as handle:
                handle.write(f"carrier.build: {carrier}\n")
            build_project(root)
            os.remove(profile_of(root))
            code, output = run_setup(runner, root, "--tool", "claude", "--from", shell_path(copy))
            code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
            check("setup: a carrier the new profile names is linked in the same run, and the first run passes "
                  "the carrier check", os.path.isfile(os.path.join(root, ".claude", "skills", carrier, "SKILL.md"))
                  and code == 0, output.strip().splitlines()[-2:])

    # item 7: update replaces the files in-process and leaves the profile alone
    with tmpdir() as root:
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        with open(profile_of(root), "a", encoding="utf-8") as handle:
            handle.write("# the person's own line\n")
        profile_before = open(profile_of(root), encoding="utf-8").read()
        gate = os.path.join(root, ".agents", "factory", "story-gate.py")
        with open(gate, "a", encoding="utf-8") as handle:
            handle.write("# an older copy\n")
        observer = os.path.join(root, ".agents", "factory", "observe.py")
        os.remove(observer)
        code, output = run_runner(project_runner(root), root, "update", "--from", source)
        check("update: gate and observer replaced, the profile left alone, and `setup --check` named at the end",
              code == 0 and "# an older copy" not in open(gate, encoding="utf-8").read() and os.path.isfile(observer)
              and open(profile_of(root), encoding="utf-8").read() == profile_before and "setup --check" in output,
              output.strip().splitlines()[-3:])

    # copies installed from a cache, at the cache's own version: `update` without --from finds the cache,
    # never the project's copies — on a version tie the copies would win by order and be refused as the source
    with tmpdir() as root, tmpdir() as home:
        cache = os.path.join(home, ".claude", "plugins", "cache", "m", "dca-factory", "1.2.3")
        write_file(cache, ".claude-plugin/plugin.json", "{}")
        shutil.copytree(source, os.path.join(cache, "skills"), symlinks=True)
        env = {"HOME": home, "FACTORY_PLUGIN_DIR": ""}
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", shell_path(os.path.join(cache, "skills")), env=env)
        gate = os.path.join(root, ".agents", "factory", "story-gate.py")
        with open(gate, "a", encoding="utf-8") as handle:
            handle.write("# an older copy\n")
        code, output = run_runner(project_runner(root), root, "update", env=env)
        check("update: copies at the cache's version are updated from the cache without --from, never from themselves",
              code == 0 and "# an older copy" not in open(gate, encoding="utf-8").read(),
              f"exit {code}; " + " / ".join(output.strip().splitlines()[-2:]))

    # a clone of a project that keeps its skill links out of git has no links: update brings them back
    if can_symlink():
        with tmpdir() as root:
            build_project(root)
            subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
            run_setup(runner, root, "--tool", "claude", "--from", source)
            write_file(root, ".gitignore", ".claude/skills/\n")
            skills = os.path.join(root, ".claude", "skills")
            os.remove(skills) if os.path.islink(skills) else shutil.rmtree(skills)
            code, output = run_runner(project_runner(root), root, "update", "--from", source)
            check("update: a clone without its ignored skill links gets them back as links",
                  code == 0 and (os.path.islink(skills) or os.path.islink(os.path.join(skills, "factory-run"))),
                  output.strip().splitlines()[-3:])

    # an update started from the project's own runner, with no --from: the skill links name the pipeline,
    # the project's skill folder does not — linked onto themselves they would become loops
    if can_symlink():
        with tmpdir() as root, tmpdir() as home:
            build_project(root)
            run_setup(runner, root, "--tool", "claude", "--from", source)
            # one link per skill, as the install makes them
            skills = os.path.join(root, ".claude", "skills")
            link = os.path.join(skills, "factory-run")
            target = os.path.dirname(os.path.realpath(link))
            before = os.path.realpath(link)
            env = {"HOME": home, "FACTORY_PLUGIN_DIR": ""}
            code, output = run_runner(project_runner(root), root, "update", "--from",
                                      os.path.join(root, ".claude", "skills"), env=env)
            check("update: a folder of the project's own links as the source (what an older runner hands over) "
                  "updates from the pipeline they lead to",
                  code == 0 and os.path.realpath(link) == before, output.strip().splitlines()[-3:])
            copy = os.path.join(root, "own-copy")
            shutil.copytree(target, copy, symlinks=True)
            code, output = run_runner(project_runner(root), root, "update", "--from", copy, env=env)
            check("update: a source inside the project is refused, and the links are left as they were",
                  code == 2 and "inside this project" in output and os.path.realpath(link) == before, output.strip())
            shutil.rmtree(copy)
            os.remove(skills) if os.path.islink(skills) else shutil.rmtree(skills)
            os.makedirs(skills)
            for name in os.listdir(target):
                os.symlink(os.path.join(target, name), os.path.join(skills, name))
            code, output = run_runner(project_runner(root), root, "update", env=env)
            check("update: from the project's own runner without --from, the links still lead to the pipeline",
                  code == 0 and os.path.realpath(link) == before and not before.startswith(os.path.realpath(root)),
                  output.strip().splitlines()[-3:])

    # item 11: the verbs mirror the skills; the old ones are gone
    with tmpdir() as root:
        env = dict(os.environ)
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", source)
        for verb in ("install", "schedule", "usage", "change", "parity"):
            code, output = run_runner(project_runner(root), root, verb)
            check(f"verbs: `{verb}` is gone", code == 2, f"exit {code}")
        code, output = run_runner(project_runner(root), root, "status", "STORY-1")
        check("verbs: `status <story>` is gone — `status --story X`", code == 2, f"exit {code}")
        code, output = run_runner(project_runner(root), root, "backlog")
        check("verbs: `backlog` shows the backlog by epic with what comes next, and works nothing off",
              code == 0 and "Backlog —" in output and "STORY-1 can start from plan" in output
              and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "STORY-1", "plan.md")),
              output.strip().splitlines()[-2:])
        code, output = run_runner(project_runner(root), root, "backlog", "--check")
        check("verbs: `backlog --check` runs the plan gate's backlog checks over every story",
              code == 0 and "1 story(ies) checked" in output, output.strip().splitlines()[-2:])
        code, output = run_runner(project_runner(root), root, "status", "--story", "STORY-1")
        check("verbs: `status --story` is the story's view", code == 0, output.strip().splitlines()[:1])
        code, output = run_runner(project_runner(root), root, "check", "--checks", "compile")
        check("verbs: `check` is the profile's checks outside a story", "gate:" in output and code in (0, 1),
              output.strip().splitlines()[-1:])
        code, output = run_runner(project_runner(root), root, "verify", "--story", "STORY-1")
        check("verbs: `verify --story` runs the observer the setup copied beside the gate",
              os.path.isfile(os.path.join(root, ".agents", "factory", "observe.py")) and "observe" in output.lower(),
              output.strip().splitlines()[:2])
        with tmpdir() as fake:
            write_file(fake, "factory-run/scripts/story-gate.py", 'VERSION = "99.0.0"\nCONTRACT = 99\n')
            write_file(fake, "factory-verify/scripts/verify.py", "print('verify: the stand-in machinery ran')\n")
            code, output = run_runner(project_runner(root), root, "verify", "--fixtures",
                                      env={"FACTORY_PLUGIN_DIR": shell_path(fake)})
            check("verbs: `verify --fixtures` runs the newest pipeline's own suite",
                  code == 0 and "stand-in machinery ran" in output, output.strip())
        settings = os.path.join(root, ".claude", "settings.json")
        data = json.load(open(settings, encoding="utf-8"))
        data["permissions"]["allow"] += ["Bash(bash .agents/factory/factory.sh usage:*)",
                                         "Bash(bash .agents/factory/factory.sh schedule:*)"]
        json.dump(data, open(settings, "w", encoding="utf-8"))
        run_runner(project_runner(root), root, "update", "--from", source)
        allow = json.load(open(settings, encoding="utf-8"))["permissions"]["allow"]
        check("permissions: update removes the retired verbs and allows the reading ones",
              not any(" usage:" in a or " schedule:" in a for a in allow)
              and all(f"factory.sh {v}:*)" in " ".join(allow) for v in ("status", "decisions", "backlog", "setup --check", "verify")),
              allow)
        hook = open(os.path.join(root, ".githooks", "pre-commit"), encoding="utf-8").read()
        check("hook: the commit hook runs `factory.sh check --staged`", "check --staged" in hook and "--change" not in hook)
        # status --brief names what detection finds and the profile lacks — not the session-start hook
        write_file(root, "build.gradle", "dependencies { testImplementation 'com.microsoft.playwright:playwright:1' }\n")
        code, output = run_runner(project_runner(root), root, "status", "--brief", env={"FACTORY_PLUGIN_DIR": source})
        check("status --brief: a line when detection finds a key the profile does not declare",
              code == 0 and "detection finds" in output and "browser" in output, output.strip().splitlines()[:1])
        gate_brief = subprocess.run([sys.executable, cli_in(root), "--status", "--brief", "--session-start"], cwd=root, capture_output=True,
                                    text=True, encoding="utf-8").stdout
        check("status --brief: the gate's session-start lines carry no detection", "detection" not in gate_brief)
    # WP-64 1a: a carrier line only for a skill installed beside the pipeline; the places from AGENTS.md
    governed = {"build.gradle": "dependencies { testImplementation 'dev.domaincentric:dca-archunit:0.6.0' }\n"}
    with tmpdir() as root:
        build_project(root)
        os.remove(profile_of(root))
        fixture(root, governed)
        run_setup(runner, root, "--tool", "claude", "--from", lone)
        lines = active_lines(profile_of(root)) or []
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("carriers: with only the pipeline installed no carrier line is active, and the first run does not "
              "stop", not any(l.startswith(("carrier.", "review.", "reviews:")) for l in lines) and code == 0,
              f"{[l for l in lines if 'carrier' in l or 'review' in l]}; exit {code}; {output.strip()[-160:]}")
    plugins_dir = os.path.dirname(os.path.dirname(source))
    installed = {name for plugin in os.listdir(plugins_dir) if plugin != "dca-factory"
                 for name in (os.listdir(os.path.join(plugins_dir, plugin, "skills"))
                              if os.path.isdir(os.path.join(plugins_dir, plugin, "skills")) else [])}
    with tmpdir() as root:
        build_project(root)
        os.remove(profile_of(root))
        fixture(root, governed)
        run_setup(runner, root, "--tool", "claude", "--from", source)
        lines = active_lines(profile_of(root)) or []
        wanted = [f"{key}: {skill}" for key, skill in (("carrier.guard", "dca-discipline"), ("review.dca", "dca-review"),
                                                         ("knowledge", "dca-knowledge"), ("carrier.plan", "dca-modelling"),
                                                         ("carrier.build", "dca-modelling"),
                                                         ("carrier.glossary", "ubiquitous-language"),
                                                         ("carrier.domain", "context-map"), ("carrier.test", "e2e-testing"),
                                                         ("review.ddd", "review-ddd"),
                                                         ("review.hexagonal", "review-hexagonal"),
                                                         ("review.clean-code", "review-clean-code"))
                  if skill in installed]
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("carriers: with the method plugins beside it, a line for every installed carrier, and the first run "
              "passes the carrier check", wanted and all(w in lines for w in wanted) and code == 0,
              f"want {wanted}; got {[l for l in lines if 'carrier' in l or 'review' in l]}; exit {code}")
        check("carriers: the built-in perspectives get their reviewer and a link, and stay out of `reviews:` — "
              "every judge runs the same one",
              "review-ddd" not in installed or (
                  all(f"{k}: {k.replace('.', '-')}" in lines for k in ("review.ddd", "review.hexagonal", "review.clean-code"))
                  and all(os.path.isfile(os.path.join(root, ".claude", "skills", n, "SKILL.md"))
                          for n in ("review-ddd", "review-hexagonal", "review-clean-code"))
                  and not any(l.startswith("reviews:") and ("ddd" in l or "hexagonal" in l) for l in lines)),
              [l for l in lines if l.startswith(("review", "reviews"))])
    with tmpdir() as root:
        write_file(root, "AGENTS.md", "# A project\n\n<!-- dca-describe: start -->\n## Project description\n\n"
                   "- product: `docs/what.md` — the product\n- tech: `project/tech.md` — the stack\n"
                   "<!-- dca-describe: end -->\n")
        run_setup(runner, root, "--tool", "none", "--from", lone)
        lines = active_lines(profile_of(root)) or []
        check("places: a place the description's AGENTS.md line names becomes a profile key; a default one does not",
              "product: docs/what.md" in lines and not any(l.startswith("tech:") for l in lines), lines)
        agents = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
        check("places: the pipeline's AGENTS.md block carries no location line of its own",
              "project/product.md" not in agents.split("<!-- dca-factory: start -->")[1], agents[-400:])
    # WP-63 7a: renamed skills — the run stops on an old name, update removes an unedited old copy
    with tmpdir() as root:
        build_project(root, profile=PROFILE + "carrier.build: ddd-modelling\nreview.domain: review-domain\n")
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run")
        check("renames: a profile naming a renamed skill stops the run, with the new line for each",
              code == 2 and "carrier.build: ddd-modelling → carrier.build: dca-modelling" in output
              and "review.domain: review-domain → review.ddd: review-ddd" in output and "── stage" not in output,
              output.strip().splitlines()[-5:])
    with tmpdir() as root, tmpdir() as home:
        cache = os.path.join(home, ".claude", "plugins", "cache", "m")
        for plugin, version, skill, body in (("software-craftsmanship", "0.5.0", "review-craft", "old v0.5.0\n"),
                                             ("software-craftsmanship", "0.5.1", "review-craft", "old v0.5.1\n"),
                                             ("software-craftsmanship", "0.5.1", "e2e-testing", "old e2e\n"),
                                             ("dca-core", "0.6.1", "ddd-modelling", "old modelling\n"),
                                             ("dca-craft", "0.6.0", "e2e-testing", "new e2e\n")):
            write_file(os.path.join(cache, plugin, version), f"skills/{skill}/SKILL.md",
                       f"---\nname: {skill}\ndescription: {body.strip()}\n---\n{body}")
            write_file(os.path.join(cache, plugin, version), ".claude-plugin/plugin.json",
                       json.dumps({"name": plugin, "version": version}))
        build_project(root, profile=PROFILE + "carrier.build: ddd-modelling\n")
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        skills_dir = os.path.join(root, ".claude", "skills")
        for skill, body in (("review-craft", "old v0.5.1\n"), ("ddd-modelling", "edited by the project\n")):
            write_file(skills_dir, f"{skill}/SKILL.md", f"---\nname: {skill}\ndescription: x\n---\n{body}")
        with open(os.path.join(skills_dir, "review-craft", "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write(open(os.path.join(cache, "software-craftsmanship", "0.5.1", "skills", "review-craft", "SKILL.md"),
                              encoding="utf-8").read())
        code, output = run_runner(project_runner(root), root, "update", "--from", source, env={"HOME": home})
        check("renames: update removes a copy byte for byte the old plugin's newest, and keeps and names an edited one",
              not os.path.exists(os.path.join(skills_dir, "review-craft"))
              and os.path.isfile(os.path.join(skills_dir, "ddd-modelling", "SKILL.md"))
              and "removed .claude/skills/review-craft" in output and "kept .claude/skills/ddd-modelling" in output,
              [l for l in output.splitlines() if "review-craft" in l or "ddd-modelling" in l])
        check("renames: update names the old profile key with its new form and writes nothing into the profile",
              "carrier.build: ddd-modelling → carrier.build: dca-modelling" in output
              and "carrier.build: ddd-modelling" in open(profile_of(root), encoding="utf-8").read(), output.strip()[-300:])
    with tmpdir() as home:
        cache = os.path.join(home, ".claude", "plugins", "cache", "m")
        write_file(os.path.join(cache, "dca-factory", "9.0.0"), ".claude-plugin/plugin.json", "{}")
        shutil.copytree(source, os.path.join(cache, "dca-factory", "9.0.0", "skills"), symlinks=True)
        for plugin, version in (("software-craftsmanship", "0.5.1"), ("dca-craft", "0.6.0")):
            write_file(os.path.join(cache, plugin, version), "skills/e2e-testing/SKILL.md",
                       f"---\nname: e2e-testing\ndescription: {plugin}\n---\n")
        with tmpdir() as root:
            build_project(root)
            run_setup(runner, root, "--tool", "codex", "--from",
                      shell_path(os.path.join(cache, "dca-factory", "9.0.0", "skills")), env={"HOME": home})
            link = os.path.join(root, ".codex", "skills", "e2e-testing")
            check("renames: a plugin left in the cache under its old name is no source — e2e-testing comes from dca-craft",
                  os.path.isdir(link) and "dca-craft" in open(os.path.join(link, "SKILL.md"), encoding="utf-8").read(),
                  os.path.realpath(link) if os.path.exists(link) else "missing")
    with tmpdir() as root:
        build_project(root, profile=PROFILE + "carrier.guard: some-guard\n")
        copy_scripts(runner, root)
        code, output = run_runner(runner, root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                                  env={"FACTORY_ISOLATION": "off"})
        prompts = {l.split()[2]: next((m for m in output.splitlines()[i + 1:i + 2]), "")
                   for i, l in enumerate(output.splitlines()) if l.startswith("── stage ")}
        check("guard: the build and tidy prompts carry the declared carrier.guard, the other stages not",
              "some-guard" in prompts.get("build", "") and "some-guard" in prompts.get("tidy", "")
              and not any("some-guard" in prompts.get(s, "") for s in ("plan", "test", "judge", "document")),
              {k: v[-90:] for k, v in prompts.items()})
    if SYMLINKS:
        with tmpdir() as root, tmpdir() as gone:
            build_project(root)
            os.makedirs(os.path.join(root, ".codex", "skills"))
            os.symlink(os.path.join(gone, "renamed-plugin", "skills", "e2e-testing"),
                       os.path.join(root, ".codex", "skills", "e2e-testing"))
            code, output = run_setup(runner, root, "--tool", "codex", "--from", source)
            link = os.path.join(root, ".codex", "skills", "e2e-testing")
            check("renames: a link into a folder that no longer exists is pruned and the skill linked afresh",
                  os.path.isfile(os.path.join(link, "SKILL.md")) and "no longer exists" in output,
                  os.readlink(link) if os.path.islink(link) else "no link")
    with tmpdir() as root:
        # adding a tool to an installed project from another pipeline version is an update nobody asked for
        build_project(root)
        run_setup(runner, root, "--tool", "none", "--from", source)
        gate_copy = os.path.join(root, ".agents", "factory", "story-gate.py")
        text = open(gate_copy, encoding="utf-8").read()
        older = re.sub(r'^VERSION = "[^"]+"', 'VERSION = "0.0.1"', text, count=1, flags=re.M)
        with open(gate_copy, "w", encoding="utf-8") as handle:
            handle.write(older)
        code, output = run_setup(runner, root, "--tool", "codex", "--from", source)
        check("setup: --tool for a new tool refuses to replace an installed pipeline of another version",
              code == 2 and "update first" in output and open(gate_copy, encoding="utf-8").read() == older
              and not os.path.exists(os.path.join(root, ".codex", "skills")), f"exit {code}; {output.strip()[-200:]}")
    if SYMLINKS:
        with tmpdir() as root:
            # a folder of the project's own that carries a pipeline skill's name, beside skills of its own
            build_project(root)
            write_file(root, ".claude/skills/stage-plan/SKILL.md", "---\nname: stage-plan\ndescription: ours\n---\n")
            write_file(root, ".claude/skills/our-skill/SKILL.md", "---\nname: our-skill\ndescription: ours\n---\n")
            code, output = run_setup(runner, root, "--tool", "claude", "--from", source)
            own = os.path.join(root, ".claude", "skills", "stage-plan")
            check("setup: a project's own skill folder with a pipeline skill's name is kept and named",
                  os.path.isdir(own) and not os.path.islink(own) and "ours" in open(os.path.join(own, "SKILL.md")).read()
                  and "kept the project's own .claude/skills/stage-plan" in output, output.strip()[-300:])
    if SYMLINKS:
        # an update from a newer version in the plugin cache: the links into the older one are the install's own
        for tool, extra in (("codex", ""), ("claude", "carrier.build: e2e-testing\n")):
            with tmpdir() as root, tmpdir() as home:
                cache = os.path.join(home, ".claude", "plugins", "cache", "m")
                def version(number, craft):
                    write_file(os.path.join(cache, "dca-factory", number), ".claude-plugin/plugin.json", "{}")
                    shutil.copytree(source, os.path.join(cache, "dca-factory", number, "skills"), symlinks=True)
                    write_file(os.path.join(cache, "dca-craft", craft), "skills/e2e-testing/SKILL.md",
                               f"---\nname: e2e-testing\ndescription: craft {craft}\n---\n")
                    return shell_path(os.path.join(cache, "dca-factory", number, "skills"))
                older = version("9.0.0", "0.6.0")
                build_project(root, profile=PROFILE + extra)
                run_setup(runner, root, "--tool", tool, "--from", older, "--link", env={"HOME": home})
                newer = version("9.1.0", "0.7.0")
                code, output = run_runner(project_runner(root), root, "update", "--from", newer, env={"HOME": home})
                skills = os.path.join(root, f".{tool}", "skills")
                where = {n: os.path.realpath(os.path.join(skills, n)) for n in ("factory-run", "e2e-testing")}
                check(f"update: {tool}'s links into an older cache version follow the newer one, the carrier's too",
                      code == 0 and "/9.1.0/" in where["factory-run"] and "/0.7.0/" in where["e2e-testing"]
                      and "kept the project's own" not in output, f"exit {code}; {where}")
        with tmpdir() as root, tmpdir() as home:
            # the links point into a version since removed from the cache, and nothing ignores them
            cache = os.path.join(home, ".claude", "plugins", "cache", "m")
            for number in ("9.0.0", "9.1.0"):
                write_file(os.path.join(cache, "dca-factory", number), ".claude-plugin/plugin.json", "{}")
                shutil.copytree(source, os.path.join(cache, "dca-factory", number, "skills"), symlinks=True)
            build_project(root)
            skills = os.path.join(root, ".claude", "skills")
            os.makedirs(skills)
            for name in os.listdir(source):
                if os.path.isdir(os.path.join(source, name)):
                    os.symlink(os.path.join(cache, "dca-factory", "9.0.0", "skills", name), os.path.join(skills, name))
            run_setup(runner, root, "--tool", "none", "--from", source)
            shutil.rmtree(os.path.join(cache, "dca-factory", "9.0.0"))
            code, output = run_runner(project_runner(root), root, "update", "--from",
                                      shell_path(os.path.join(cache, "dca-factory", "9.1.0", "skills")), env={"HOME": home})
            run_skill = os.path.join(skills, "factory-run", "SKILL.md")
            check("update: a tool whose skill links are broken is updated, not skipped",
                  code == 0 and os.path.isfile(run_skill) and "/9.1.0/" in os.path.realpath(run_skill),
                  f"exit {code}; {os.path.realpath(run_skill)}; {output.strip()[-300:]}")
    # the install's list names its entries in both modes; the mode follows the source; a project's own
    # skill with a pipeline name survives setup and update; .gitignore carries one line per link
    def manifest_of(root, tool="claude"):
        path = os.path.join(root, f".{tool}", "skills", ".dca-factory-skills")
        return open(path, encoding="utf-8").read().splitlines() if os.path.isfile(path) else []

    def ignore_lines(root):
        path = os.path.join(root, ".gitignore")
        return open(path, encoding="utf-8").read().splitlines() if os.path.isfile(path) else []

    if SYMLINKS:
        with tmpdir() as root:
            build_project(root)
            write_file(root, ".claude/skills/factory-run/SKILL.md", "---\nname: factory-run\ndescription: PROJECT OWN\n---\n")
            code, output = run_setup(runner, root, "--tool", "claude", "--from", source)
            own = os.path.join(root, ".claude", "skills", "factory-run", "SKILL.md")
            code2, output2 = run_runner(project_runner(root), root, "update", "--from", source)
            skills = os.path.join(root, ".claude", "skills")
            links = [n for n in os.listdir(skills) if os.path.islink(os.path.join(skills, n))]
            check("install: a project's own folder with a pipeline skill's name survives setup and update, the links stay links",
                  code == 0 and code2 == 0 and "PROJECT OWN" in open(own, encoding="utf-8").read()
                  and "kept the project's own .claude/skills/factory-run" in output2 and len(links) >= 13
                  and "mode: link" in manifest_of(root) and "factory-run" not in manifest_of(root),
                  f"exit {code}/{code2}; links {len(links)}; {manifest_of(root)[:3]}; {output2.strip()[-300:]}")
            check("install: .gitignore carries one line per link, none for the folder or the project's own skill",
                  ".claude/skills/stage-plan" in ignore_lines(root) and ".claude/skills/factory-run" not in ignore_lines(root)
                  and ".claude/skills" not in ignore_lines(root) and ".claude/skills/" not in ignore_lines(root),
                  ignore_lines(root)[:5])
        with tmpdir() as root, tmpdir() as home:
            cache = os.path.join(home, ".claude", "plugins", "cache", "m")
            write_file(os.path.join(cache, "dca-factory", "9.0.0"), ".claude-plugin/plugin.json", "{}")
            shutil.copytree(source, os.path.join(cache, "dca-factory", "9.0.0", "skills"), symlinks=True)
            cached = shell_path(os.path.join(cache, "dca-factory", "9.0.0", "skills"))
            build_project(root)
            code, output = run_setup(runner, root, "--tool", "claude", "--from", cached, env={"HOME": home})
            skills = os.path.join(root, ".claude", "skills")
            plan = os.path.join(skills, "stage-plan")
            check("install: from a plugin cache the skills are copies, listed as such, and nothing is ignored",
                  code == 0 and os.path.isdir(plan) and not os.path.islink(plan) and "mode: copy" in manifest_of(root)
                  and "source: cache" in manifest_of(root) and "plugin cache" in output and not ignore_lines(root),
                  f"exit {code}; {manifest_of(root)[:3]}; {output.strip()[-200:]}")
            code, output = run_runner(project_runner(root), root, "update", "--from", source, "--link", env={"HOME": home})
            check("update: --link switches the project's copies to links into a checkout, listed and ignored",
                  code == 0 and os.path.islink(plan) and "mode: link" in manifest_of(root)
                  and "source: checkout" in manifest_of(root) and ".claude/skills/stage-plan" in ignore_lines(root),
                  f"exit {code}; {manifest_of(root)[:3]}; {output.strip()[-200:]}")
            code, output = run_runner(project_runner(root), root, "update", "--from", cached, "--link", env={"HOME": home})
            check("update: a link into a checkout follows to a cache when named, and the report warns about the cache",
                  code == 0 and "/9.0.0/" in os.path.realpath(plan) and "plugin cache" in output
                  and "kept the project's own" not in output, f"exit {code}; {os.path.realpath(plan)}; {output.strip()[-300:]}")
            code, output = run_runner(project_runner(root), root, "update", "--from", cached, "--copy", env={"HOME": home})
            check("update: --copy switches back to copies and drops the ignore lines",
                  code == 0 and os.path.isdir(plan) and not os.path.islink(plan) and "mode: copy" in manifest_of(root)
                  and ".claude/skills/stage-plan" not in ignore_lines(root), f"exit {code}; {ignore_lines(root)}")
        with tmpdir() as root:
            build_project(root)
            run_setup(runner, root, "--tool", "none", "--from", source)
            os.makedirs(os.path.join(root, ".claude", "skills"))
            os.symlink(os.path.join(root, "nowhere"), os.path.join(root, ".claude", "skills", "gone-skill"))
            gate = os.path.join(root, ".agents", "factory", "story-gate.py")
            result = subprocess.run([sys.executable, gate, "--status", "--brief"], cwd=root, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace")
            check("status: --brief names a skill link that points nowhere and the update that relinks it",
                  "gone-skill points nowhere" in result.stdout and "/factory-update" in result.stdout,
                  result.stdout.strip()[-300:] + result.stderr.strip()[-200:])
    with tmpdir() as root:
        # a copy from before the list: taken over only byte for byte, an edited one is the project's
        build_project(root)
        run_setup(runner, root, "--tool", "claude", "--from", source, "--copy")
        skills = os.path.join(root, ".claude", "skills")
        os.remove(os.path.join(skills, ".dca-factory-skills"))
        with open(os.path.join(skills, "stage-plan", "SKILL.md"), "a", encoding="utf-8") as handle:
            handle.write("# edited by the project\n")
        code, output = run_runner(project_runner(root), root, "update", "--from", source)
        check("update: a copy from before the list is taken over only byte for byte; an edited one is kept and named",
              code == 0 and "edited by the project" in open(os.path.join(skills, "stage-plan", "SKILL.md"), encoding="utf-8").read()
              and "kept the project's own .claude/skills/stage-plan" in output and "stage-plan" not in manifest_of(root)
              and "stage-build" in manifest_of(root), f"exit {code}; {output.strip()[-300:]}")
    with tmpdir() as root:
        build_project(root)
        code, output = run_setup(runner, root, "--tool", "claude", "--from", source)
        check("install: for Claude Code the report names the second listing under the plugin's namespace",
              "dca-factory:<skill>" in output, output.strip()[-300:])
    # one parser: the runner asks the cli, which reads with the gate's readers — and the gate only decides
    def cli(root, *argv):
        done = subprocess.run([sys.executable, cli_in(root), *argv], cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return done.returncode, done.stdout.strip()

    with tmpdir() as root:
        build_project(root, profile=PROFILE + 'model.claude.tidy: "haiku"\nmodel.claude: sonnet\n'
                                             "carrier.build: dca-core:dca-modelling\nreview.ddd: review-ddd\n")
        run_setup(runner, root, "--tool", "none", "--from", source)
        heads = cli(root, "--command-heads")[1].split()
        check("cli: --get, --command-heads, --carriers, --carrier-lines and --model read the profile as the gate does",
              cli(root, "--get", "carrier.build")[1] == "dca-core:dca-modelling"
              and cli(root, "--get", "nothing-here")[1] == ""
              and heads and len(heads) == len(set(heads)) and all(not h.startswith("{{") for h in heads)
              and cli(root, "--carriers")[1].split("\n") == ["dca-modelling", "review-ddd"]
              and "carrier.build dca-core:dca-modelling" in cli(root, "--carrier-lines")[1].split("\n")
              and cli(root, "--model", "claude", "tidy")[1] == "haiku" and cli(root, "--model", "claude", "build")[1] == "sonnet"
              and cli(root, "--model", "codex", "build")[1] == "",
              f"{heads}; {cli(root, '--carriers')[1]!r}; {cli(root, '--model', 'claude', 'tidy')[1]!r}")
        write_file(root, ".dca-factory/runs/STORY-1/judge.md", "## Verdict\nverdict: `changes-requested`\n")
        write_file(root, ".dca-factory/runs/STORY-1/build.md", "# Build\n\n## needs-human\n- decision: STORY-1-01. The browser…\n")
        write_file(root, ".dca-factory/runs/STORY-1/tidy.md", "# Tidy\n\n## needs-human\n(none)\n")
        write_file(root, "project/epics/sample/STORY-1.decisions/01.md", "---\nid: STORY-1-01\nstory: STORY-1\nstage: build\n---\n\n# Q?\n")
        write_file(root, "project/epics/sample/STORY-1.decisions/02.md",
                   "---\nid: STORY-1-02\nstory: STORY-1\nstage: plan\n---\n\n# Q?\n\n## Answer\nanswer: yes\nby: x\nat: y\n")
        asks = cli(root, "--needs-human", ".dca-factory/runs/STORY-1/build.md", "--story", "STORY-1")
        check("cli: --verdict, --needs-human and --open-decisions read the stage files and the records as the gate does",
              cli(root, "--verdict", "STORY-1")[1] == "changes-requested" and cli(root, "--verdict", "STORY-9")[1] == ""
              and asks == (0, "STORY-1-01\tbuild\tproject/epics/sample/STORY-1.decisions/01.md")
              and cli(root, "--needs-human", ".dca-factory/runs/STORY-1/tidy.md")[0] == 1
              and cli(root, "--open-decisions", "STORY-1")[1].split("\n") == ["project/epics/sample/STORY-1.decisions/01.md"],
              f"{asks}; {cli(root, '--open-decisions', 'STORY-1')}")
        # a pair of one release, or no run: the runner refuses a cli of another version and a missing one
        project_cli = cli_in(root)
        text = open(project_cli, encoding="utf-8").read()
        with open(project_cli, "w", encoding="utf-8") as handle:
            handle.write(text.replace("VERSION = _gate.VERSION", 'VERSION = "0.0.1"', 1))
        code, output = run_runner(project_runner(root), root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                                  env={"FACTORY_ISOLATION": "off"})
        check("runner: a cli of another version than the gate stops a run before its first stage",
              code == 2 and "one release, two files" in output, f"exit {code}; {output.strip()[-200:]}")
        os.remove(project_cli)
        code, output = run_runner(project_runner(root), root, "run", "--story", "STORY-1", "--tool", "claude", "--dry-run",
                                  env={"FACTORY_ISOLATION": "off"})
        check("runner: without the cli beside the gate nothing is started, and the update is named",
              code == 2 and "no factory-cli.py beside the gate" in output, f"exit {code}; {output.strip()[-200:]}")
        code, output = run_runner(project_runner(root), root, "update", "--from", source)
        stamp = open(os.path.join(root, ".agents", "factory", "gate.installed"), encoding="utf-8").read()
        check("update: puts the cli beside the gate, and the record names the files of the release",
              code == 0 and os.path.isfile(project_cli) and "files: story-gate.py factory-cli.py" in stamp,
              f"exit {code}; {stamp.strip()}")
        handed = subprocess.run([sys.executable, os.path.join(root, ".agents", "factory", "story-gate.py"),
                                 "--status", "--brief"], cwd=root, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        check("gate: a flag that moved to the cli is handed over, so an older caller still gets its answer",
              handed.returncode == 0 and handed.stdout.startswith("factory:"), handed.stdout.strip()[:200])
    gate_text = open(os.path.join(os.path.dirname(runner), "story-gate.py"), encoding="utf-8").read()
    cli_text = open(os.path.join(os.path.dirname(runner), "factory-cli.py"), encoding="utf-8").read()
    runner_text = open(runner, encoding="utf-8").read()
    observe_text = open(os.path.join(os.path.dirname(runner), "..", "..", "factory-verify", "scripts", "observe.py"),
                        encoding="utf-8").read()
    check("gate: carries no colour code, no price and no session-log path — those are the cli's",
          "\\x1b[" not in gate_text and "def money(" not in gate_text and ".claude/projects" not in gate_text
          and "def money(" in cli_text and "\\x1b[" in cli_text)
    parsed = [l.strip()[:80] for l in runner_text.splitlines()
              if "sed -n" in l and not l.strip().startswith("#")
              and re.search(r"profile|judge\.md|needs-human|\$DECISIONS|carrier\.|model\\\.", l)]
    check("runner: parses no profile, stage file or record itself — every read goes through the cli", not parsed, parsed[:3])
    duplicated = [n for n in ("CRITERION", "MAPPING_ROW", "SELECTOR") if re.search(rf"^{n} = re\.compile", observe_text, re.M)]
    check("observe: defines no reader the gate has — it imports the gate's",
          not duplicated and "def front_matter(" not in observe_text and "story_gate" in observe_text, duplicated)
    shutil.rmtree(lone_home, ignore_errors=True)

    failures = [name for name, ok, _ in results if not ok]
    print(f"\nverify: {len(results) - len(failures)}/{len(results)} setup cases behaved as specified")

    return failures


# --- WP-75: one owner per place — the story carries its state, the run folder is protocol ---------------
OLD_PROFILE = ".agents/factory/factory.profile.yaml"


def gate_module(path):
    """The gate as a module, for the one function a case calls directly (the front-matter writer)."""
    spec = importlib.util.spec_from_file_location("story_gate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_layout(root, delivered="2026-09-20T10:00:00Z"):
    """A project as dca-factory 0.48 left it: the profile under .agents/factory/, project/backlog/, a decisions
    store, run artefacts under tasks/ — beside the project's own files under tasks/."""
    write_file(root, "project/backlog/sample/epic.md", EPIC)
    write_file(root, "project/backlog/sample/STORY-1.md", STORY)
    write_file(root, "project/backlog/sample/STORY-2.md", story("STORY-2", ["STORY-1"]))
    write_file(root, "project/product.md", PRODUCT)
    write_file(root, "project/tech.md", TECH)
    write_file(root, OLD_PROFILE, "contract: 9\ncompile: true\nbacklog: project/backlog\n")
    write_file(root, ".agents/factory/decisions/STORY-1-01.md", DECISION + ANSWER)
    write_file(root, ".agents/factory/decisions/STORY-1-accept-1.md",
               "---\nid: STORY-1-accept-1\nstory: STORY-1\nstage: document\nkind: acceptance\n"
               "asked: 2026-09-20T09:00:00Z\ndigest: none\n---\n\n# Accept STORY-1?\n\n## Answer\n"
               "answer: accepted\nby: a-human\nat: 2026-09-20T09:30:00Z\n")
    for name, text in (("plan.md", PLAN_APPLIED), ("tests.md", TESTS), ("build.md", "# Build\n"), ("tidy.md", "# Tidy\n"),
                       ("judge.md", "## Verdict\nverdict: pass\n"), ("document.md", DOCUMENT),
                       (".delivered", delivered + "\n"), (".story-digest", "0" * 64 + "\n"),
                       (".verify/journal.tsv", "2026-09-20T09:00:00Z\tgate\tdocument\texit=0\n")):
        write_file(root, f"tasks/STORY-1/{name}", text)
    write_file(root, "tasks/STORY-2/plan.md", PLAN_APPLIED.replace("STORY-1", "STORY-2"))
    write_file(root, "tasks/STORY-2/.story-digest", hashlib.sha256(
        open(os.path.join(root, "project/backlog/sample/STORY-2.md"), "rb").read()).hexdigest() + "\n")
    write_file(root, "tasks/prd.md", "# The author's PRD, from before the pipeline\n")
    write_file(root, "tasks/notes/todo.txt", "not the factory's\n")
    write_file(root, ".gitattributes", "*.png binary\ntasks/**/.verify/journal.tsv merge=union\n")
    write_file(root, "AGENTS.md", "# AGENTS.md\n")


def verify_places(args):
    """The cases of the layout with one owner per place."""
    expectations = []
    gate = gate_module(args.gate)

    def cli(root, *argv):
        return subprocess.run([sys.executable, args.cli, *argv], cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def gate_run(root, *argv):
        return subprocess.run([sys.executable, args.gate, *argv], cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    # ids are unique project-wide: a second story under the same id is refused, naming both files
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", []), extra_sources=(
            ("project/epics/other/epic.md", EPIC.replace("id: sample", "id: other")),
            ("project/epics/other/STORY-2.md", story("STORY-2").replace("epic: sample", "epic: other"))))
        checked = gate_run(root, "--check-backlog")
        planned = gate_run(root, "--story", "STORY-2", "--stage", "plan")
        rows, nxt, _w, listing = schedule_of(args.gate, root)
        both = ("project/epics/other/STORY-2.md", "project/epics/sample/STORY-2.md")
        expectations.append(("ids: a story id used twice is refused by the backlog check, the plan gate and the schedule, "
                             "naming both files",
                             checked.returncode == 1 and all(p in checked.stdout for p in both) and "not unique" in checked.stdout
                             and planned.returncode == 1 and all(p in planned.stdout for p in both)
                             and rows.get("STORY-1", ("",))[0] == "ready"
                             and sum(1 for line in listing.splitlines() if "not unique" in line and "STORY-2" in line) == 2
                             and nxt.startswith("STORY-1"),
                             f"check {checked.returncode}: {checked.stdout.strip()[-200:]} | plan {planned.returncode} | "
                             f"{listing.strip()[-300:]}"))

    # the run folder is protocol: deleted after two deliveries, nothing about state changes
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", ["STORY-1"]), ("STORY-3", ["STORY-2"]),
                        story=delivered_story(STORY, "2026-09-21T10:00:00Z"),
                        extra_sources=(("project/epics/sample/STORY-2.md",
                                        delivered_story(story("STORY-2", ["STORY-1"]), "2026-09-22T10:00:00Z")),
                                       (".dca-factory/runs/STORY-1/document.md", DOCUMENT),
                                       (".dca-factory/runs/STORY-2/document.md", DOCUMENT),
                                       (".dca-factory/runs/STORY-2/.verify/journal.tsv",
                                        "2026-09-22T09:00:00Z\tstage-start\tplan\ttool=x\n"
                                        "2026-09-22T09:10:00Z\tstage-end\tplan\texit=0\n")))
        before = schedule_of(args.gate, root)
        status_before = cli(root, "--status", "--part", "backlog", "--format", "json").stdout
        shutil.rmtree(os.path.join(root, ".dca-factory"))
        after = schedule_of(args.gate, root)
        status_after = cli(root, "--status", "--part", "backlog", "--format", "json").stdout
        states = lambda text: [(r["story"], r["state"], r["delivered"]) for r in json.loads(text or "{}").get("rows", [])]
        expectations.append(("runs: deleting the run folder after two delivered stories changes no state — the schedule, "
                             "the dependencies and the status read the same, only the tokens are gone",
                             before[0] == after[0] and before[1] == after[1] == "STORY-3 plan"
                             and after[0].get("STORY-2") == ("delivered", None) and states(status_before) == states(status_after)
                             and [s for _st, s, _d in states(status_after)][:2] == ["delivered", "delivered"],
                             f"{before[0]} → {after[0]}; next {before[1]} → {after[1]}; {states(status_after)}"))

    # code in the checkout that no run folder claims: nothing starts on top of it — unless a story was delivered
    # after HEAD, whose code waits for its commit
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", []), extra_sources=((".gitignore", "green/\n"),))
        for command in (["init", "-q"], ["add", "-A"],
                        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        clean = schedule_of(args.gate, root)
        os.remove(os.path.join(root, "src", "test", "java", "com", "example", "WidgetUnitTest.java"))
        gone = schedule_of(args.gate, root)
        write_file(root, "src/main/java/com/example/Thing.java", "class Thing {}\n")
        stray = schedule_of(args.gate, root)
        mark_delivered(root, "STORY-1", (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        delivered_since = schedule_of(args.gate, root)
        expectations.append(("runs: a changed source file that no story's run folder claims stops the schedule and is named — "
                             "a file that is gone does not; a story delivered since the last commit explains it, and the "
                             "next story runs",
                             clean[1].startswith("STORY-1") and gone[1].startswith("STORY-1") and stray[1].startswith("none")
                             and "no story's run folder claims" in stray[1]
                             and "src/main/java/com/example/Thing.java" in stray[1] and delivered_since[1] == "STORY-2 plan",
                             f"clean {clean[1]!r}; gone {gone[1]!r}; stray {stray[1]!r}; since {delivered_since[1]!r}"))

    # the gate's one write into a story keeps everything else byte for byte, line endings included
    with tmpdir() as root:
        crlf = STORY.replace("\n", "\r\n")
        path = os.path.join(root, "story.md")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(crlf)
        gate.write_story_fields(path, status="delivered", delivered="2026-09-28T10:00:00Z")
        with open(path, encoding="utf-8", newline="") as handle:
            written = handle.read()
        gate.write_story_fields(path, status="approved", delivered=None)
        with open(path, encoding="utf-8", newline="") as handle:
            restored = handle.read()
        expectations.append(("story: `status: delivered` and `delivered:` are written into the front matter and taken out "
                             "again with every other byte as it was, line endings included",
                             written == crlf.replace("status: approved\r\n",
                                                     "status: delivered\r\ndelivered: 2026-09-28T10:00:00Z\r\n")
                             and restored == crlf,
                             f"{written[:160]!r}"))

    # an older layout is named and not read: the story gate fails on it, the backlog check notes it
    with tmpdir() as root:
        build_project(root)
        os.makedirs(os.path.join(root, ".agents", "factory"), exist_ok=True)
        os.replace(os.path.join(root, "dca-factory.profile.yaml"), os.path.join(root, OLD_PROFILE))
        os.rename(os.path.join(root, "project", "epics"), os.path.join(root, "project", "backlog"))
        planned = gate_run(root, "--story", "STORY-1", "--stage", "plan")
        checked = gate_run(root, "--check-backlog")
        expectations.append(("layout: the profile under .agents/factory/ and project/backlog/ are named as the older layout "
                             "with the update that migrates it, and the story gate does not run on them",
                             planned.returncode == 1 and "gate:fail layout" in planned.stdout
                             and "factory.sh update" in planned.stdout and "dca-factory.profile.yaml" in planned.stdout
                             and "project/backlog/ is now project/epics/" in planned.stdout
                             and "gate:note layout" in checked.stdout,
                             planned.stdout.strip()[-400:]))

    # the migration: once, idempotent, and the project's own files under tasks/ untouched
    with tmpdir() as root:
        old_layout(root)
        foreign_before = {p: open(os.path.join(root, p), "rb").read() for p in ("tasks/prd.md", "tasks/notes/todo.txt")}
        first = cli(root, "--migrate-layout")
        digest_after_first = tree_digest(root)
        second = cli(root, "--migrate-layout")
        rows, nxt, _w, listing = schedule_of(args.gate, root)
        story_1 = open(os.path.join(root, "project", "epics", "sample", "STORY-1.md"), encoding="utf-8").read()
        profile = open(os.path.join(root, "dca-factory.profile.yaml"), encoding="utf-8").read()
        digest_2 = open(os.path.join(root, ".dca-factory", "runs", "STORY-2", ".story-digest"), encoding="utf-8").read().strip()
        expectations.append(("migrate: the profile moves to the root with `epics:` and the contract, project/backlog/ becomes "
                             "project/epics/, each record lands beside its story, the run artefacts move and the delivery "
                             "goes into the story — the project's own files under tasks/ untouched, a second run moves nothing",
                             first.returncode == 0 and "status: delivered\ndelivered: 2026-09-20T10:00:00Z" in story_1
                             and "epics: project/epics" in profile and "backlog:" not in profile and "contract: 10" in profile
                             and not os.path.exists(os.path.join(root, OLD_PROFILE))
                             and os.path.isfile(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"))
                             and os.path.isfile(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "accept-1.md"))
                             and not os.path.exists(os.path.join(root, ".agents", "factory", "decisions"))
                             and os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-1", "document.md"))
                             and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".delivered"))
                             and not os.path.exists(os.path.join(root, "tasks", "STORY-1"))
                             and all(open(os.path.join(root, p), "rb").read() == c for p, c in foreign_before.items())
                             and digest_2 == story_digest(os.path.join(root, "project", "epics", "sample", "STORY-2.md"))
                             and ".dca-factory/runs/**/.verify/journal.tsv merge=union"
                             in open(os.path.join(root, ".gitattributes"), encoding="utf-8").read()
                             and "nothing to move" in second.stdout and tree_digest(root) == digest_after_first
                             and rows.get("STORY-1") == ("delivered", None) and rows.get("STORY-2", ("",))[0] == "in-progress",
                             f"{first.stdout.strip()[-500:]} | second: {second.stdout.strip()} | {rows}"))

    # one architecture command: the profile's and the conventions' compared, a difference named, never fixed
    with tmpdir() as root:
        build_project(root)
        write_file(root, ".agents/dca/conventions.md", "## Resolved configuration\n\nverify_command: ./gradlew archTest\n")
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("architecture: ./gradlew test-architecture\n")
        differs = cli(root, "--drift")
        brief = cli(root, "--status", "--brief")
        write_file(root, ".agents/dca/conventions.md",
                   "## Resolved configuration\n\nverify_command: ./gradlew test-architecture\n")
        same = cli(root, "--drift")
        brief_same = cli(root, "--status", "--brief")
        expectations.append(("drift: `architecture:` in the profile and `verify_command:` in the conventions file are compared — "
                             "a difference is named by --drift and by status --brief with both commands, equal ones are silent",
                             differs.returncode == 1 and "./gradlew archTest" in differs.stdout
                             and "./gradlew test-architecture" in differs.stdout
                             and ".agents/dca/conventions.md" in brief.stdout and "archTest" in brief.stdout
                             and same.returncode == 0 and same.stdout.strip() == "" and "archTest" not in brief_same.stdout
                             and "verify_command" not in brief_same.stdout,
                             f"{differs.stdout.strip()} | {brief.stdout.strip()[-300:]}"))
    return expectations


def main(argv=None):
    parser = argparse.ArgumentParser(description="verify the factory")
    parser.add_argument("--gate", default=DEFAULT_GATE)
    parser.add_argument("--cli", default=DEFAULT_CLI, help="the CLI beside the gate (default: beside --gate)")
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument("--group", choices=("all", "checks", "runner", "setup"), default="all",
                        help="run one group only: the gate's and the schedule's checks, the runner, the install")
    parser.add_argument("--junit", metavar="FILE", help="write every case as a JUnit XML report")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    # Every case runs in a throwaway directory, so a path given relative to the caller's directory
    # would resolve to nothing there — and the whole suite would fail with the gate merely missing.
    args.gate = os.path.abspath(args.gate)
    args.cli = os.path.abspath(args.cli) if args.cli != DEFAULT_CLI else cli_of(args.gate)
    args.runner = os.path.abspath(args.runner)

    if not os.path.isfile(args.gate):
        print(f"verify: no gate at {args.gate}")
        return 2
    if not os.path.isfile(args.cli):
        print(f"verify: no cli at {args.cli} — the gate and the cli are one release, in one folder")
        return 2
    try:
        return run_groups(args)
    finally:
        if args.junit:
            write_junit(args.junit)


def write_junit(path):
    """One testsuite per group, one testcase per case; a failure carries the detail."""
    from xml.sax.saxutils import quoteattr
    groups = {}
    for group, name, ok, detail in RESULTS:
        groups.setdefault(group, []).append((name, ok, detail))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<testsuites>"]
    for group, cases in groups.items():
        failed = sum(1 for _, ok, _ in cases if not ok)
        lines.append(f'  <testsuite name={quoteattr(group)} tests="{len(cases)}" failures="{failed}">')
        for name, ok, detail in cases:
            lines.append(f'    <testcase classname={quoteattr(group)} name={quoteattr(name)}>')
            if not ok:
                lines.append(f'      <failure message={quoteattr(str(detail)[:400])}/>')
            lines.append("    </testcase>")
        lines.append("  </testsuite>")
    lines.append("</testsuites>")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run_groups(args):
    if args.group in ("runner", "setup"):
        return run_runner_groups(args, [], args.group)

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
        (Case("plan: a context whose name is only part of another's or of a sentence is not on the map", "plan", 1,
              must_fail=("context-map",)),
         dict(context_map="# Context map\n\nWidgets are handled elsewhere.\n\n| Context |\n|---|\n| Widgets Admin |\n")),
        (Case("plan: no context map at all is skipped and named", "plan", 0,
              must_skip=("context-map",)),
         dict(context_map=None)),
        (Case("plan: three rounds stop the run", "plan", 1, must_fail=("rounds",)),
         dict(rounds=3)),
        (Case("plan: no project description is a note, not a failure", "plan", 0,
              text=("no product description at project/product.md", "no technical description at project/tech.md")),
         dict()),
        (Case("plan: a complete product and technical description pass", "plan", 0, must_pass=("product", "tech")),
         dict(extra_sources=(("project/product.md", PRODUCT), ("project/tech.md", TECH)))),
        (Case("plan: a technical description with an empty heading is refused", "plan", 1,
              must_fail=("tech",), text=("empty `## Persistence`",)),
         dict(extra_sources=(("project/tech.md", TECH.replace("One relational database.", "<!-- where -->")),))),
        (Case("plan: a `tech:` that names no file is refused", "plan", 1, must_fail=("tech",)),
         dict(profile=PROFILE + "tech: docs/tech.md\n")),
        (Case("plan: the designed map is read first — a context designed and not built yet passes", "plan", 0,
              must_pass=("context-map",), text=("is on project/domain.md",)),
         dict(context_map="# Context map\n\n| Context |\n|---|\n| Something else |\n",
              extra_sources=(("project/domain.md", "# Designed\n\n| Context |\n|---|\n| Widgets |\n"),))),
        (Case("plan: a context the designed map lacks is refused, whatever the generated map says", "plan", 1,
              must_fail=("context-map",)),
         dict(extra_sources=(("project/domain.md", "# Designed\n\n| Context |\n|---|\n| Something else |\n"),))),
        (Case("plan: a `domain:` that names no file is refused", "plan", 1, must_fail=("context-map",)),
         dict(profile=PROFILE + "domain: docs/designed.md\n")),
        (Case("plan: a product scope with an empty heading is refused, comments do not count", "plan", 1,
              must_fail=("product",), text=("empty `## Look and feel`",)),
         dict(extra_sources=(("project/product.md", PRODUCT.replace(
             "Plain, readable, the project's own stylesheet.", "<!-- style direction -->")),))),
        (Case("plan: a product scope missing a heading is refused", "plan", 1,
              must_fail=("product",), text=("missing `## Qualities`",)),
         dict(extra_sources=(("project/product.md", PRODUCT.replace("## Qualities", "## Quality")),))),
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
        # --- contract 9: the happy path, the levels, the journey ---------------
        (Case("plan: a story with no happy path is refused", "plan", 1, must_fail=("happy-path",),
              text=("0 scenarios marked `(happy path)`",)),
         dict(story=STORY.replace(" (happy path):", ":"))),
        (Case("plan: a story with two happy paths is refused", "plan", 1, must_fail=("happy-path",),
              text=("2 scenarios marked",)),
         dict(story=STORY.replace("- shows-the-thing:", "- shows-the-thing (happy path):"))),
        (Case("plan: a scenario marked happy path passes and keeps its key", "plan", 0,
              must_pass=("happy-path", "story"), text=("happy path: shows-nothing-when-empty",)),
         dict(story=STORY_SCENARIOS)),
        (Case("plan: a contract-8 profile is not held to the happy path", "plan", 0, must_skip=("happy-path",)),
         dict(story=STORY.replace(" (happy path):", ":"), profile=PROFILE + "contract: 8\n")),
        (Case("plan: a journey without depends_on is refused", "plan", 1, must_fail=("journey",)),
         dict(story=STORY.replace("status: approved\n", "status: approved\nkind: journey\n")
              .replace(" (happy path):", ":"))),
        (Case("plan: a journey over delivered stories needs no happy path", "plan", 0, must_pass=("journey",)),
         dict(story=STORY.replace("status: approved\n", "status: approved\nkind: journey\n")
              .replace(" (happy path):", ":").replace("depends_on: []", "depends_on: [STORY-0]"))),
        (Case("test: an end-user test for a scenario that is not the happy path is refused", "test", 1,
              must_fail=("levels",), text=("shows-the-thing (com.example.WidgetPageTest#showsTheThing)",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"))),
        (Case("test: an end-user test without its scenario's title as display name is refused", "test", 1,
              must_fail=("test-titles",), text=('"Shows the thing"',)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"),
              story=STORY.replace(" (happy path):", ":").replace("- shows-the-thing:", "- shows-the-thing (happy path):"),
              extra_sources=(("src/test-pages/java/com/example/WidgetPageTest.java",
                              "class WidgetPageTest { void showsTheThing() {} }\n"),))),
        (Case("test: a scenario's `Title:` line is the title its end-user test carries", "test", 0,
              must_pass=("test-titles",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"),
              story=STORY_SCENARIOS.replace("#### shows-the-thing\n", "#### shows-the-thing (happy path)\nTitle: The list shows what is recorded\n")
              .replace("#### shows-nothing-when-empty (happy path)", "#### shows-nothing-when-empty"),
              extra_sources=(("src/test-pages/java/com/example/WidgetPageTest.java",
                              "class WidgetPageTest { @DisplayName(\"The list shows what is recorded\") void showsTheThing() {} }\n"),))),
        (Case("test: a `Title:` with a quote matches the escaped literal its end-user test carries", "test", 0,
              must_pass=("test-titles",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"),
              story=STORY_SCENARIOS.replace("#### shows-the-thing\n", "#### shows-the-thing (happy path)\nTitle: The list shows a \"Recorded\" heading\n")
              .replace("#### shows-nothing-when-empty (happy path)", "#### shows-nothing-when-empty"),
              extra_sources=(("src/test-pages/java/com/example/WidgetPageTest.java",
                              "class WidgetPageTest { @DisplayName(\"The list shows a \\\"Recorded\\\" heading\") void showsTheThing() {} }\n"),))),
        (Case("test: an end-user test the plan gave browser-only passes the level check", "test", 0,
              must_pass=("levels",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"), extra_sources=(
             (".dca-factory/runs/STORY-1/plan.md", "# Plan\n\n## Acceptance criteria\n- shows-the-thing: The reader sees the "
                                       "thing. → level: browser-only (a script draws it after load)\n"),))),
        (Case("test: a title only in a comment is not the end-user test's display name", "test", 1,
              must_fail=("test-titles",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"),
              story=STORY.replace(" (happy path):", ":").replace("- shows-the-thing:", "- shows-the-thing (happy path):"),
              extra_sources=(("src/test-pages/java/com/example/WidgetPageTest.java",
                              "class WidgetPageTest {\n  // Shows the thing is covered elsewhere\n  void showsTheThing() {}\n}\n"),))),
        (Case("test: a test of the same simple name in another package does not stand in for the mapped one",
              "test", 1, must_fail=("tests-exist",)),
         dict(extra_sources=(("src/test/java/com/example/WidgetUnitTest.java", "class WidgetUnitTest { }\n"),
                             ("src/test/java/com/other/WidgetUnitTest.java",
                              "package com.other;\nclass WidgetUnitTest { void showsNothingWhenEmpty() {} }\n")))),
        (Case("test: the happy path's end-user test passes the level check", "test", 0, must_pass=("levels",)),
         dict(profile=PROFILE.replace("test.pages:", "e2eTest:"),
              story=STORY.replace(" (happy path):", ":").replace("- shows-the-thing:", "- shows-the-thing (happy path):"))),
        # --- adoption: existing behaviour into the backlog, with evidence -----
        (Case("plan: an adopted story passes the plan gate, held to no happy path", "plan", 0,
              must_pass=("approved",), must_skip=("happy-path",)),
         dict(story=ADOPTED)),
        (Case("test: an adopted story's tests are green at the test gate", "test", 0, must_pass=("tests-green",)),
         dict(story=ADOPTED, green=both_green)),
        (Case("adopt: every scenario on a green existing test and a judge's pass adopts the story", "adopt", 0,
              must_pass=("tests-green", "adopt-judged"), must_skip=("break-proof",)),
         dict(story=ADOPTED, green=both_green, extra_sources=((".dca-factory/runs/STORY-1/judge.md", "# Judge\n\nverdict: pass\n"),))),
        (Case("adopt: without a judge's pass nothing is adopted", "adopt", 1, must_fail=("adopt-judged",)),
         dict(story=ADOPTED, green=both_green)),
        (Case("adopt: a red test is not adopted", "adopt", 1, must_fail=("tests-green",)),
         dict(story=ADOPTED, green=both_green[:1], extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),))),
        (Case("adopt: a characterization test without its break is refused", "adopt", 1, must_fail=("break-proof",),
              text=("no break at",)),
         dict(story=ADOPTED, green=both_green, tests=TESTS + CHARACTERIZED,
              extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),))),
        (Case("adopt: a characterization test red under its break passes, on a scratch copy", "adopt", 0,
              must_pass=("break-proof",), text=("red under its break",)),
         dict(story=ADOPTED, green=both_green, tests=TESTS + CHARACTERIZED,
              extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),
                             (".dca-factory/runs/STORY-1/breaks/com.example.WidgetPageTest--showsTheThing.patch", BREAK_THE_THING)))),
        (Case("adopt: a characterization test named by its simple class is found and broken as the table's", "adopt", 0,
              must_pass=("break-proof",), text=("com.example.WidgetPageTest#showsTheThing (shows-the-thing): red",)),
         dict(story=ADOPTED, green=both_green, tests=TESTS + "\n## Characterization\n- WidgetPageTest#showsTheThing\n",
              extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),
                             (".dca-factory/runs/STORY-1/breaks/WidgetPageTest--showsTheThing.patch", BREAK_THE_THING)))),
        (Case("adopt: a break written with Windows line endings still applies", "adopt", 0,
              must_pass=("break-proof",), text=("red under its break",)),
         dict(story=ADOPTED, green=both_green, tests=TESTS + CHARACTERIZED,
              extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"),
                             (".dca-factory/runs/STORY-1/breaks/com.example.WidgetPageTest--showsTheThing.patch",
                              BREAK_THE_THING.replace("\n", "\r\n"))))),
        (Case("adopt: a break that leaves the test green is refused and names it", "adopt", 1,
              must_fail=("break-proof",), text=("stays green under its break",)),
         dict(story=ADOPTED, green=both_green, tests=TESTS + CHARACTERIZED,
              extra_sources=((".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n"), ("unrelated.txt", "a\n"),
                             (".dca-factory/runs/STORY-1/breaks/com.example.WidgetPageTest--showsTheThing.patch", BREAK_NOTHING)))),
        (Case("adopt: a break that changes nothing is refused where the code sits in a package named `tasks`",
              "adopt", 1, must_fail=("break-proof",), text=("stays green under its break",)),
         dict(story=ADOPTED, profile=PACKAGED_PROFILE, tests=TESTS + CHARACTERIZED, extra_sources=PACKAGED_SOURCES)),
        (Case("test: a journey's test is green at its gate, the inverse of a story", "test", 0,
              must_pass=("tests-green",)),
         dict(story=STORY.replace("status: approved\n", "status: approved\nkind: journey\n")
              .replace("depends_on: []", "depends_on: [STORY-0]"), green=both_green)),
        # --- the test gate ------------------------------------------------
        (Case("test: every criterion mapped and red passes", "test", 0,
              must_pass=("tests-mapped", "tests-exist", "compiles", "tests-red")),
         dict()),
        (Case("test: a tests.md without `## Files` is refused once the stage's changes are recorded", "test", 1,
              must_fail=("files-listed",)),
         dict(tests=TESTS.split("\n## Files")[0] + "\n", extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-test.txt", "modified\tsrc/test/java/com/example/WidgetUnitTest.java\n"),))),
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
        (Case("test: a display name with an escaped quote matches the report's unescaped name", "test", 0,
              must_pass=("tests-red",), text=("display name declared in the code",)),
         dict(story=STORY.replace("- shows-the-thing: The reader sees the thing.\n", ""),
              tests="# Tests\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n"
                    "| shows-nothing-when-empty | com.example.WidgetUnitTest#showsNothingWhenEmpty |\n",
              profile="compile: true\ntest: sh quoted-runner.sh\ncovers.test: **\n"
                      'filterFlag: --select\nfilterFormat: "{class}#{method}"\narchitecture: true\n',
              extra_sources=(
                  ("src/test/java/com/example/WidgetUnitTest.java",
                   "class WidgetUnitTest {\n"
                   '  @DisplayName("shows a \\"Discover\\" row")\n'
                   "  void showsNothingWhenEmpty() {}\n}\n"),
                  ("quoted-runner.sh",
                   '#!/bin/sh\nmkdir -p build/test-results/run\n'
                   'printf \'<testsuite><testcase classname="com.example.WidgetUnitTest" \''
                   '\'name="shows a &quot;Discover&quot; row"><failure>not yet</failure></testcase>\''
                   '\'</testsuite>\\n\' > build/test-results/run/TEST-WidgetUnitTest.xml\n'
                   'echo "1 test ran"\nexit 1\n'),
              ))),
        # --- the version contract -----------------------------------------
        # Two numbers, two jobs: the *contract* says whether this gate can read the project's
        # files at all, so a mismatch is a refusal. The script's *version* is provenance and an
        # update hint, which only the installer can see — the runner checks that, not the gate.
        (Case("contract: a profile written for a newer gate is refused", "plan", 1,
              must_fail=("contract",), text=("run `factory.sh update`",)),
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
              text=("STORY-1-01 is open", "project/epics/sample/STORY-1.decisions/01.md", "`by:` and `at:`")),
         with_decisions(("STORY-1-01", DECISION), plan=PLAN_ASKING)),
        (Case("decisions: a stage that writes on after the id on its decision line still names that record", "test", 1,
              must_fail=("decisions",), text=("STORY-1-01 is open",)),
         with_decisions(("STORY-1-01", DECISION),
                        plan=PLAN_ASKING.replace("decision: STORY-1-01\n", "decision: STORY-1-01. The archive is open.\n"))),
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
              must_fail=("decisions",), text=("is found by its file name",)),
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
        (Case("decisions: a judge's story conflict answered for the plan stage lets the plan gate through",
              "plan", 0, text=("the plan stage runs next and applies it",)),
         dict(extra_sources=(("project/epics/sample/STORY-1.decisions/01.md",
                              CONFLICT.replace("stage: test", "stage: plan") + ANSWER),
                             (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED.replace("Decision STORY-1-01 answered b: ", "")),
                             (".dca-factory/runs/STORY-1/judge.md", JUDGE_CONFLICT)))),
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
        (Case("document: a judge who asked for changes delivers nothing", "document", 1,
              must_fail=("story-pass",), text=("verdict: changes-requested",)),
         dict(document=DOCUMENT, extra_sources=((".dca-factory/runs/STORY-1/judge.md", "## Verdict\nverdict: changes-requested\n"),))),
        (Case("document: a judge's file without a verdict delivers nothing", "document", 1,
              must_fail=("story-pass",), text=("`verdict: none`",)),
         dict(document=DOCUMENT, extra_sources=((".dca-factory/runs/STORY-1/judge.md", ""),))),
        (Case("document: a story changed after it was planned delivers nothing", "document", 1,
              must_fail=("story-pass",), text=("changed after it was planned",)),
         dict(document=DOCUMENT, extra_sources=((".dca-factory/runs/STORY-1/.story-digest", "0" * 64),))),
        (Case("test: a test recorded red before may be green when its expectation changed on a decision",
              "test", 0, must_pass=("tests-red", "decisions"), text=("expectation changed on decision STORY-1-01",)),
         dict(tests=TESTS_ON_DECISION, green=both_green, ledger=both_green,
              **with_decisions(("STORY-1-01", CONFLICT + ANSWER), plan=PLAN_APPLIED))),
        (Case("test: an answer a later stage asked for that changes a test (`applies: test`) is the test stage's",
              "test", 0, must_pass=("tests-red", "decisions"), text=("expectation changed on decision STORY-1-01",)),
         dict(tests=TESTS_ON_DECISION, green=both_green, ledger=both_green,
              **with_decisions(("STORY-1-01", CONFLICT.replace("stage: test", "stage: build")
                                + ANSWER.replace("answer: b\n", "answer: b\napplies: test\n")), plan=PLAN_APPLIED))),
        (Case("test: without that decision, green before the build is still refused", "test", 1,
              must_fail=("tests-red",), text=("passes before the build stage",)),
         dict(green=both_green, ledger=both_green)),
        (Case("test: a story planned again keeps the tests an earlier pass saw red and built green",
              "test", 0, must_pass=("tests-red",), text=("recorded red in an earlier pass",)),
         dict(green=both_green, ledger=both_green, extra_sources=((".dca-factory/runs/STORY-1/build.md", "# Build\n"),))),
        (Case("test: a story running again for a human's correction keeps the tests it had met, green",
              "test", 0, must_pass=("tests-red",), text=("expectation changed on decision STORY-1-accept-1",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             ("project/epics/sample/STORY-1.decisions/accept-1.md",
              "---\nid: STORY-1-accept-1\nstory: STORY-1\nstage: document\nkind: acceptance\n"
              "asked: 2026-09-25T15:00:00Z\ndigest: none\n---\n\n# Accept STORY-1?\n\n## Answer\n"
              "answer: correction: two cards on m\nby: a-human\nat: 2026-09-25T15:10:00Z\n"),))),
        # --- the build gate -----------------------------------------------
        # --- the hand-over names what the stage changed ------------------------
        (Case("build: a hand-over that lists every changed file passes the files check", "build", 0,
              must_pass=("files-listed",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\nmodified\tsrc/main/Page.java\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Changed\n\n## Files\n\n- `src/main/Thing.java` — new\n"
                                        "- `src/main/Page.java` — shows it\n")))),
        (Case("build: a changed file the hand-over does not list is refused, named", "build", 1,
              must_fail=("files-listed",), text=("src/main/Page.java",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\nmodified\tsrc/main/Page.java\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Changed\n| File | Why |\n|---|---|\n| `src/main/Thing.java` | new |\n")))),
        (Case("build: a hand-over without a Files section is refused", "build", 1,
              must_fail=("files-listed",), text=("has no `## Files` section",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Criteria\n")))),
        (Case("build: without a changed-files record the files check is skipped and named", "build", 0,
              must_skip=("files-listed",)),
         dict(green=both_green, ledger=both_green)),
        (Case("build: a stage running its own gate inside its window is told the gate after its end checks the "
              "files, even with an earlier round's record there", "build", 0,
              must_skip=("files-listed",), text=("still open",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Other.java\n"),
             (".dca-factory/runs/STORY-1/.verify/journal.tsv",
              "2026-09-26T13:55:20.100Z\tstage-start\tbuild\ttool=claude-session\n")))),
        (Case("build: after a shared builder its record is the one checked — a file it changed that no hand-over "
              "lists is refused", "build", 1, must_fail=("files-listed",), text=("src/main/Page.java",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-builder.txt", "added\tsrc/main/Thing.java\nmodified\tsrc/main/Page.java\n"),
             (".dca-factory/runs/STORY-1/.verify/journal.tsv", "2026-09-27T10:00:00.000Z\tstage-start\tbuilder\ttool=claude\n2026-09-27T10:30:00.000Z\tstage-end\tbuilder\texit=0\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Files\n\n- `src/main/Thing.java` — new\n")))),
        (Case("build: after a shared builder a file listed by any of its hand-overs passes, and an older per-stage "
              "record is not read", "build", 0, must_pass=("files-listed",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Stale.java\n"),
             (".dca-factory/runs/STORY-1/.verify/changed-builder.txt", "added\tsrc/test/ThingTest.java\nadded\tsrc/main/Thing.java\n"),
             (".dca-factory/runs/STORY-1/.verify/journal.tsv",
              "2026-09-26T09:00:00.000Z\tstage-start\tbuild\ttool=claude\n2026-09-26T09:10:00.000Z\tstage-end\tbuild\texit=0\n"
              + "2026-09-27T10:00:00.000Z\tstage-start\tbuilder\ttool=claude\n2026-09-27T10:30:00.000Z\tstage-end\tbuilder\texit=0\n"),
             (".dca-factory/runs/STORY-1/tidy.md", "## Files\n\n- `src/test/ThingTest.java` — renamed a helper\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Files\n\n- `src/main/Thing.java` — new\n")))),
        (Case("build: outside git the stage's changes are not observed — the files check is skipped and says why, "
              "never passed as `0 files changed`", "build", 0,
              must_skip=("files-listed",), text=("not a git repository",), absent=("list(s) the 0 file(s)",)),
         dict(green=both_green, ledger=both_green, prepare=marked_build_outside_git,
              extra_sources=((".dca-factory/runs/STORY-1/build.md", "## Files\n\n- nothing listed\n"),))),
        (Case("tidy: a stage that changed no file needs no `## Files` section", "tidy", 0,
              must_pass=("files-listed",), text=("changed no file",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-tidy.txt", ""),
             (".dca-factory/runs/STORY-1/tidy.md", "# Tidy\n\nNothing to tidy: the build left no duplication.\n")))),
        (Case("build: a backticked route or `/` in a table's *Why* cell is prose, not a listed path", "build", 0,
              must_pass=("files-listed",), absent=("listed but not changed",)),
         dict(green=both_green, ledger=both_green, extra_sources=(
             (".dca-factory/runs/STORY-1/.verify/changed-build.txt", "added\tsrc/main/Thing.java\n"),
             (".dca-factory/runs/STORY-1/build.md", "## Files\n\n| File | Why |\n|---|---|\n"
                                        "| `src/main/Thing.java` | handles `GET /`, redirects to `/` |\n")))),
        (Case("plan: a gate run over a delivered story checks it and leaves its marks as they are", "plan", 0,
              text=("is delivered — checked",)),
         dict(story=delivered_story(STORY, "2026-09-27T10:00:00Z"),
              extra_sources=((".dca-factory/runs/STORY-1/.story-digest", "the-digest-of-the-delivery\n"),),
              after=lambda root: [f"{name} was rewritten" for name, kept in
                                  ((".story-digest", "the-digest-of-the-delivery"),)
                                  if open(os.path.join(root, ".dca-factory/runs/STORY-1", name), encoding="utf-8").read().strip() != kept])),
        (Case("document: a gate run over a delivered story checks it and leaves the delivery mark as it is",
              "document", 0, text=("is delivered — checked",)),
         dict(green=both_green, ledger=both_green, document=DOCUMENT,
              story=delivered_story(STORY, "2026-09-27T10:00:00Z"),
              after=lambda root: [] if "delivered: 2026-09-27T10:00:00Z" in open(
                  os.path.join(root, "project/epics/sample/STORY-1.md"), encoding="utf-8").read() else ["delivered: was rewritten"])),
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
        (Case("document: a bare file name with a line is a citation — it resolves from the project root or is refused",
              "document", 1, must_fail=("documented",), text=("WidgetUnitTest.java:1",)),
         dict(green=both_green, ledger=both_green,
              document=DOCUMENT.replace("read `README.md:1`", "read `WidgetUnitTest.java:1`"))),
        (Case("document: the same citation written from the project root resolves", "document", 0,
              must_pass=("documented",)),
         dict(green=both_green, ledger=both_green,
              document=DOCUMENT.replace("read `README.md:1`", "read `src/test/java/com/example/WidgetUnitTest.java:1`"))),
        (Case("test: a test red on an action's timeout, with no expectation, is red and noted as such", "test", 0,
              must_pass=("tests-red",), text=("red on a timeout, not on an assertion",)),
         dict(timeouts=("com.example.WidgetPageTest#showsTheThing",))),
        (Case("test: a test red on its assertion gets no timeout note", "test", 0,
              must_pass=("tests-red",), absent=("red on a timeout",)),
         dict()),
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
            # `prepare` runs the CLI's marks or a git command over the fixture before the gate; `after`
            # looks at what the gate left behind and returns the problems it finds.
            fixture = dict(fixture)
            prepare, after = fixture.pop("prepare", None), fixture.pop("after", None)
            build_project(root, **fixture)
            if prepare:
                prepare(root, args)
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
            for needle in case.absent:
                if needle in output:
                    problems.append(f"the report says {needle!r}")
            if after:
                problems.extend(after(root))
            note_result(case.name, not problems, "; ".join(problems))
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
            ("STORY-9-01", DECISION.replace("STORY-1", "STORY-9")),
            extra_sources=(("project/epics/sample/STORY-9.md", story("STORY-9")),)))
        listing = subprocess.run([sys.executable, args.cli, "--list-decisions"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        inbox = json.loads(subprocess.run([sys.executable, args.cli, "--list-decisions", "--format", "json"], cwd=root,
                                          capture_output=True, text=True, encoding="utf-8").stdout or "{}")
        states = [r["state"] for r in inbox.get("records", [])]
        expectations = [
            ("inbox: every record is listed, open first, then draft, answered, applied",
             states == ["open", "open", "draft", "answered", "applied"], f"states in order: {states}"),
            ("inbox: an answered record shows its answer and who gave it",
             "→ b (the-expert)" in listing.stdout, listing.stdout[-600:]),
            ("inbox: the summary counts what waits on a human, and Next says how to answer — in an agent and in a shell",
             "5 records · 3 wait for you" in listing.stdout and "/factory-decisions" in listing.stdout
             and "under `## Answer`" in listing.stdout, listing.stdout[-600:]),
        ]
        one_story = subprocess.run([sys.executable, args.cli, "--list-decisions", "--story", "STORY-9"],
                                   cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations.append(("inbox: --story narrows the listing to one story",
                             "STORY-9-01" in one_story.stdout and "STORY-1-01" not in one_story.stdout
                             and "1 record · 1 waits for you" in one_story.stdout,
                             one_story.stdout.strip().splitlines()[-1:]))
        for name, ok, detail in expectations:
            print(f"  {'ok   ' if ok else 'FAIL '} {name}")
            note_result(name, ok, detail)
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
        expectations.append(("change: without `required:` nothing is mandatory, and what it skipped is named",
                             code == 0 and "test" in verdicts["skip"] and "nothing is mandatory" in output,
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
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("e2eTest: sh runner.sh src/test-pages/java\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: a test command that is not required and ran nothing is named, not failed",
                             code == 0 and "(e2eTest) exited 0, but no report" in output
                             and "e2eTest" not in output.split("gate:pass policy")[1].split("\n")[0],
                             output.strip().splitlines()[-4:]))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("format: false\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: with a policy, a red optional check is reported and does not decide",
                             code == 0 and "optional (not in `required:`), so it does not decide" in output,
                             output.strip().splitlines()[-4:]))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
            handle.write("required: compile test e2eTest format\n")
        code, output = run_change(args.gate, root)
        expectations.append(("change: `required:` binds each test command by its own key",
                             code == 1 and "(e2eTest) exited 0, but no report" in output
                             and "format" in checks_by_verdict(output)["fail"]
                             and "ran 1 case(s)" in output, output.strip().splitlines()[-4:]))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as handle:
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
        copy_scripts(args.gate, root)
        shutil.copy(args.runner, os.path.join(root, ".agents", "factory", "factory.sh"))   # the hook calls `check`
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
        note_result(name, ok, detail)
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
        note_result(name, ok, detail)
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
        ledger = open(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".tests-red"), encoding="utf-8").read()
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
        os.makedirs(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions"), exist_ok=True)
        with open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"), "w", encoding="utf-8") as handle:
            handle.write(CONFLICT + ANSWER)
        with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", "tests.md"), "a", encoding="utf-8") as handle:
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
        backlog_project(root, extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                             (".dca-factory/runs/STORY-1/.verify/journal.tsv",
                                              "t\tstage-start\tplan\ttool=x\nt\tstage-end\tplan\texit=0\n"
                                              "t\tstage-start\ttest\ttool=x\n")))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: each story shows the stage invocations its journal recorded",
                             "2 stage invocation(s)" in output, [l for l in output.splitlines() if "STORY-1" in l]))
    expectations += verify_places(args)
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
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
        read = lambda *a: subprocess.run([sys.executable, args.cli, "--usage-from", *a], capture_output=True,
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
        note_result(name, ok, detail)
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
        journal = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:00:30.000Z\tstage-start\tplan\ttool=claude-session\n")
        environment = dict(os.environ, CLAUDE_CODE_SESSION_ID=session, CLAUDE_CONFIG_DIR=home)
        # the mark runs "now"; the log is from the past, so the window is closed by hand as the mark would
        subprocess.run([sys.executable, args.cli, "--stage-end", "plan", "--story", "S-1"], cwd=root,
                       env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = open(journal, encoding="utf-8").read().splitlines()
        recorded = [l for l in lines if "\tusage\t" in l]
        if recorded:
            fixed = recorded[0].split("\t")
            fixed = [("window=2026-09-23T10:00:30.000Z/2026-09-23T10:05:00.000Z" if f.startswith("window=") else f)
                     for f in fixed]
            with open(journal, "w", encoding="utf-8") as handle:
                handle.write("\n".join(l for l in lines if "\tusage\t" not in l) + "\n" + "\t".join(fixed) + "\n")
        plan = usage_json(args.gate, root, "S-1", environment).get("plan", {})
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
        whole = subprocess.run([sys.executable, args.cli, "--usage-from", "codex-session", rollout],
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:01:00.000Z\tstage-start\ttest\ttool=codex-session\n"
                         f"2026-09-23T10:03:00.000Z\tusage\ttest\ttool=codex-session\t"
                         f"window=2026-09-23T10:01:00.000Z/2026-09-23T10:03:00.000Z\tlog={rollout}\n")
        test_stage = usage_json(args.gate, root, "S-1").get("test", {})
        # the next stage mark writes what can be read into the journal; `--usage` itself only reads
        subprocess.run([sys.executable, args.cli, "--stage-start", "document", "--story", "S-1"], cwd=root,
                       env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations = [
            ("usage in a session: the mark records the window and the session's id — no path, which would name "
             "the machine and the person in a committed file",
             bool(recorded) and "window=" in recorded[0] and "session=claude:0000-session" in recorded[0]
             and "log=" not in recorded[0] and home not in recorded[0], recorded[:1]),
            ("usage in a session: Claude's log is read for the window, each response once, subagents included, "
             "synthetic entries left out",
             [plan.get(k) for k in ("runs", "measured", "input", "cache_read", "cache_write", "output")]
             == [1, 1, 2, 200, 20, 57], plan),
            ("usage in a session: a session log has no cost, and the report says so rather than 0.00",
             plan.get("priced") == 0, plan),
            ("usage in a session: at the next stage mark the numbers are written into the journal and the "
             "machine-local log path leaves it",
             any("output=57" in l and "log=" not in l for l in open(journal, encoding="utf-8").read().splitlines()),
             [l for l in open(journal, encoding="utf-8").read().splitlines() if "usage" in l][:1]),
            ("usage in a session: Codex's running totals are differenced over the window",
             [test_stage.get(k) for k in ("input", "cache_read", "cache_write", "output")] == [800, 1200, 0, 30],
             test_stage),
            ("usage from a whole old log: a Codex session is read to its last total",
             whole.startswith("model=codex-model\tinput=1000\tcache_read=2000\tcache_write=0\toutput=40"), whole),
        ]
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- status: what runs, what waits, every story, the cost — in one look -------------------------
    with tmpdir() as root:
        backlog_project(root, ("STORY-2", []), extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_ASKING),
            ("project/epics/sample/STORY-1.decisions/01.md", DECISION),
            (".dca-factory/runs/STORY-2/.verify/journal.tsv",
             "2026-09-23T10:00:00Z\tstage-start\tplan\ttool=x\n2026-09-23T10:01:00Z\tstage-end\tplan\texit=0\n"
             "2026-09-23T10:01:00Z\tusage\tplan\ttool=x\tmodel=m\tinput=10\tcache_read=0\tcache_write=0\toutput=90\tcost=0.01\n"
             "2026-09-23T10:02:00Z\tstage-start\ttest\ttool=x\n")))
        run = lambda *more: subprocess.run([sys.executable, args.cli, "--status", *more], cwd=root,
                                           capture_output=True, text=True, encoding="utf-8").stdout
        out = run()
        part = lambda text, name, until: text.split(name, 1)[1].split(until, 1)[0] if name in text else ""
        story2 = next((l for l in part(out, "Backlog", "Tokens").splitlines() if "STORY-2" in l), "")
        expectations = [
            ("status: a stage with a start and no end is shown with when it started (UTC) — as interrupted once it is "
             "older than a stage may take, on top as well",
             "✗ STORY-2   test   since 2026-09-23 10:02 UTC · never ended — possibly interrupted" in part(out, "Running", "Backlog")
             and "✗ STORY-2" in part(out, "Waiting for you", "Running")
             and re.search(r"✗ STORY-2\s+interrupted\?\s+test", story2) is not None,
             part(out, "Waiting for you", "Backlog") + story2),
            ("status: what needs a person is listed first, with the story and what to do",
             re.search(r"\? STORY-1\s+waiting for your answer\n\s+agent\s+/factory-decisions\n\s+shell\s+write the answer "
                       r"into project/epics/sample/STORY-1\.decisions/01\.md", part(out, "Waiting for you", "Running")) is not None,
             part(out, "Waiting for you", "Running")),
            ("status: one row per story, grouped under its epic; its tokens by class, per epic and in total, with the cost",
             "sample" in part(out, "Backlog", "Tokens") and "STORY-1" in part(out, "Backlog", "Tokens")
             and re.search(r"^\s+↳ STORY-2\s+2\s+10\s+90\s+0\s+0\s+100\s+0\.01$", part(out, "Tokens", "\n" + "─" * 72), re.M)
             and re.search(r"^\s+sample\s+2\s+10\s+90\s+0\s+0\s+100\s+0\.01$", part(out, "Tokens", "\n" + "─" * 72), re.M)
             and re.search(r"^\s+total\s+2\s+10\s+90\s+0\s+0\s+100\s+0\.01$", part(out, "Tokens", "\n" + "─" * 72), re.M),
             part(out, "Tokens", "\n" + "─" * 72)),
            ("status: the same files give the same text — no clock in the view without --live",
             out == run(), ""),
            ("status: no colour when the output is not a terminal, colour when asked for",
             "\x1b[" not in out and "\x1b[" in run("--color", "always"), ""),
        ]
        md = run("--format", "md")
        cells = lambda text: sorted(c.strip() for l in text.splitlines() if l.startswith("|") and "---" not in l
                                    for c in l.strip("|").split("|")[1:])
        text_rows = [l for l in part(out, "Backlog", "Tokens").splitlines() if re.match(r"^\s+[?!✗▶✓·] STORY", l)]
        md_rows = [l for l in md.splitlines() if re.match(r"^\| [👀❓⛔⏳✅➖] STORY", l)]
        expectations += [
            ("status --format md: the same rows as the terminal view, with the session's marks",
             len(text_rows) == len(md_rows) == 2 and "⛔ STORY-2" in md and "❓ STORY-1" in md
             and all(r.split("|")[2].strip() in out for r in md_rows), "\n".join(md_rows)),
            ("status --format json: the model, readable by a tool",
             json.loads(run("--format", "json"))["total"] == 2, ""),
        ]
        helper = lambda *more: subprocess.run([sys.executable, args.cli, "--help-view", *more], cwd=root,
                                              capture_output=True, text=True, encoding="utf-8").stdout
        help_text, help_md = helper(), helper("--format", "md")
        flow = json.loads(helper("--format", "json"))["flow"]
        resolved = lambda argument: subprocess.run([sys.executable, args.cli, "--resolve", argument], cwd=root,
                                                   capture_output=True, text=True, encoding="utf-8")
        by_name, typo, wish, nothing = (resolved(a) for a in ("story-2", "STROY-2", "show the newest items first", ""))
        expectations += [
            ("resolve: one word naming a story is that story, whatever its case",
             by_name.returncode == 0 and by_name.stdout.strip() == "story STORY-2", by_name.stdout),
            ("resolve: one word naming no story is refused with the ids there are — never a new story",
             typo.returncode == 2 and typo.stdout.startswith("unknown STROY-2") and "STORY-1, STORY-2" in typo.stdout,
             typo.stdout),
            ("resolve: more than one word is a wish, nothing is the backlog",
             wish.stdout.strip() == "wish" and nothing.stdout.strip() == "backlog"
             and wish.returncode == nothing.returncode == 0, wish.stdout + nothing.stdout),
            ("help: a wish is one of the commands, agent only",
             "`/factory-run <your words>` | — needs an agent session" in help_md, help_md[:600]),
        ]
        expectations += [
            ("help: the flow in a fixed order, one place marked — where this project is now: an open question",
             [f["step"] for f in flow] == ["start", "set up", "write stories", "run", "answer or accept"]
             and [f["mark"] for f in flow if f["mark"] not in ("none", "done")] == ["question"]
             and {f["step"]: f["mark"] for f in flow}["set up"] == "done"
             and flow[-1]["mark"] == "question", flow),
            ("help: every command in its agent and its shell form, the marks and the files",
             all(c in help_text for c in ("/factory-status", "factory.sh status", "/factory-decisions",
                                          "factory.sh decisions", "factory.sh help", "Marks", "Files", "Next"))
             and "`factory.sh backlog --check`" in help_md and "| 👀 | `!` |" in help_md
             and "**waits for your answer**" in help_md and help_md.count("`/factory-setup`") == 2, help_md[:900]),
            ("help: the same files give the same text, in the terminal and in the session",
             help_text == helper() and help_md == helper("--format", "md") and "\x1b[" not in help_text, ""),
        ]
        story_view = run("--story", "STORY-2")
        stages = part(story_view, "Stages", "\n" + "─" * 72)
        expectations += [
            ("status of one story: each stage its own row with runs, the four token classes, the cost, and a total",
             re.search(r"^\s+plan\s+1\s+1 min\s+10\s+90\s+0\s+0\s+100\s+0\.01$", stages, re.M)
             and re.search(r"^\s+test\s+1 \(1 not measured\)\s+—\s+—\s+—\s+—\s+—\s+not measured\s+—$", stages, re.M)
             and re.search(r"^\s+total\s+2\s+1 min\s+10\s+90\s+0\s+0\s+100\s+0\.01$", stages, re.M), stages),
            ("status of one story: its passes and what waits", "Passes" in story_view and "1  first delivery" in story_view,
             story_view),
        ]
    with tmpdir() as root:
        # switched off: the gate records the stage and reads no session log
        journal = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:00:30.000Z\tstage-start\tplan\ttool=claude-session\n")
        environment = dict(os.environ, CLAUDE_CODE_SESSION_ID="0000-session", FACTORY_SESSION_USAGE="off")
        out = subprocess.run([sys.executable, args.cli, "--stage-end", "plan", "--story", "S-1"], cwd=root,
                             env=environment, capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("usage in a session: FACTORY_SESSION_USAGE=off records the stage as unknown and "
                             "no session", "switched off" in out and "session=" not in open(journal, encoding="utf-8").read(),
                             out.strip()))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write("sessionUsage: off\n")
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:06:00.000Z\tstage-start\ttest\ttool=claude-session\n")
        out = subprocess.run([sys.executable, args.cli, "--stage-end", "test", "--story", "S-1"], cwd=root,
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
        journal = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:01:00.000Z\tstage-start\tplan\ttool=codex-session\n"
                         "2026-09-23T10:03:00.000Z\tusage\tplan\ttool=codex-session\t"
                         "window=2026-09-23T10:01:00.000Z/2026-09-23T10:03:00.000Z\tsession=codex:abc-123\n")
        plan = usage_json(args.gate, root, "S-1", dict(os.environ, CODEX_HOME=codex_home)).get("plan", {})
        expectations.append(("usage in a session: a Codex session is found by its id alone",
                             plan.get("runs") == 1 and plan.get("measured") == 1 and plan.get("output") == 7, plan))
    with tmpdir() as root:
        # a union merge: one branch read the window, the other still points at the log; lines interleave
        journal = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "journal.tsv")
        os.makedirs(os.path.dirname(journal))
        window = "window=2026-09-23T10:00:00.000Z/2026-09-23T10:05:00.000Z"
        with open(journal, "w", encoding="utf-8") as handle:
            handle.write("2026-09-23T10:05:00.000Z\tstage-end\tplan\texit=0\n"
                         f"2026-09-23T10:05:00.000Z\tusage\tplan\ttool=claude-session\tmodel=m\tinput=1\t"
                         f"cache_read=0\tcache_write=0\toutput=9\t{window}\n"
                         f"2026-09-23T10:05:00.000Z\tusage\tplan\ttool=claude-session\t{window}\tlog=/gone.jsonl\n"
                         "2026-09-23T10:00:00.000Z\tstage-start\tplan\ttool=claude-session\n")
        plan = usage_json(args.gate, root, "S-1").get("plan", {})
        status_out = subprocess.run([sys.executable, args.cli, "--status"], cwd=root, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace").stdout
        expectations.append(("usage after a union merge: one window read on one branch and pending on the other "
                             "counts once", plan.get("runs") == 1 and plan.get("measured") == 1
                             and plan.get("output") == 9, plan))
        expectations.append(("status after a union merge: a stage is running only if its start is the latest "
                             "event by time, not by line", "Nothing is running." in status_out,
                             status_out[:400]))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
        if not ok:
            print(f"          {detail}")
            failures.append((name, [], ""))

    # --- one worker per checkout: the claim, and what the schedule does with a running stage -----------
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        claim = lambda owner, *more: subprocess.run([sys.executable, args.cli, "--claim", owner], cwd=root,
                                                    env=dict(os.environ, **dict(more)), capture_output=True,
                                                    text=True, encoding="utf-8")
        first, second, again = claim("worker-a"), claim("worker-b"), claim("worker-a")
        taken = claim("worker-b", ("FACTORY_STALE_AFTER", "0"))
        lock_in_git = os.path.isfile(os.path.join(root, ".git", "dca-factory-worker.lock"))
        subprocess.run([sys.executable, args.cli, "--release", "worker-b"], cwd=root, capture_output=True)
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
        before = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root, capture_output=True, text=True,
                                encoding="utf-8").stdout
        subprocess.run([sys.executable, args.cli, "--listening"], cwd=root, env=environment, capture_output=True)
        after = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8").stdout
        ended = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", env=dict(os.environ, FACTORY_LISTEN_STALE="60")).stdout
        brief = subprocess.run([sys.executable, args.cli, "--status", "--brief"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8").stdout
        expectations += [
            ("listening: before any look the status says no session has looked",
             "no session has looked at the backlog" in before, before[-400:]),
            ("listening: a look is shown with the session and how long ago",
             "listening: claude-session:listening-session, last look 0 min ago" in after
             and "listening:" in brief, after[-400:]),
            ("listening: it lives in the git directory, never committed",
             os.path.isfile(os.path.join(root, ".git", "dca-factory-listener.json")), ""),
        ]
        write_old = os.path.join(root, ".git", "dca-factory-listener.json")
        data = json.load(open(write_old, encoding="utf-8"))
        data["beat"] = "2026-01-01T00:00:00Z"
        json.dump(data, open(write_old, "w", encoding="utf-8"))
        old = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root, capture_output=True, text=True,
                             encoding="utf-8").stdout
        expectations.append(("listening: a long silence reads as a loop that has probably ended",
                             "probably ended" in old, old[-400:]))
    with tmpdir() as root:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        backlog_project(root, ("STORY-2", []), extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
            (".dca-factory/runs/STORY-1/.verify/journal.tsv", f"{now}\tstage-start\ttest\ttool=x\n"),))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a stage that started and has not ended is running, and nothing else starts",
                             rows.get("STORY-1", ("",))[0] == "running" and nxt.startswith("none")
                             and "STORY-1 is running" in nxt, f"{rows.get('STORY-1')}, next: {nxt}"))
        completed = subprocess.run([sys.executable, args.cli, "--schedule"], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", env=dict(os.environ, FACTORY_STALE_AFTER="0"))
        expectations.append(("schedule: a start with no sign of life is taken as interrupted, and the story is "
                             "named again", "possibly interrupted" in completed.stdout
                             and "next: STORY-1" in completed.stdout, completed.stdout.strip().splitlines()[-1:]))
    with tmpdir() as root:
        build_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run([sys.executable, args.cli, "--claim", "someone-else"], cwd=root, capture_output=True)
        out = subprocess.run([sys.executable, args.cli, "--stage-start", "plan", "--story", "STORY-1"], cwd=root,
                             env=dict(os.environ, CLAUDE_CODE_SESSION_ID="this-session"), capture_output=True,
                             text=True, encoding="utf-8")
        expectations.append(("claim: a session's stage mark is refused while another worker holds the checkout",
                             out.returncode == 3 and not os.path.exists(
                                 os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "journal.tsv")), out.stdout))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
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
            with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", "plan.md"), "w", encoding="utf-8") as handle:
                handle.write(PLAN_APPLIED + "\n" + plan_extra)
            if record:
                os.makedirs(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions"), exist_ok=True)
                with open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"), "w",
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
             lambda t: t.replace("isEmpty()", "size() == 0 || true"), True, "pass"),
            ("a plan's question answered `applies: test` changes no test the plan does not list",
             lambda t: t.replace("isEmpty()", "size() == 0 || true"),
             CONFLICT.replace("stage: test", "stage: plan") + ANSWER.replace("answer: b\n", "answer: b\napplies: test\n"),
             "fail")):
        with tmpdir() as root:
            build_project(root, extra_sources=((unit, old_test),))
            for command in (["init", "-q"], ["add", "-A"],
                            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
                subprocess.run(["git", *command], cwd=root, capture_output=True)
            subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
            baseline = os.path.isfile(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".tests-baseline"))
            if change is None:
                os.remove(os.path.join(root, unit))
            else:
                with open(os.path.join(root, unit), "w", encoding="utf-8") as handle:
                    handle.write(change(old_test))
            if decided:
                os.makedirs(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions"), exist_ok=True)
                with open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"), "w",
                          encoding="utf-8") as handle:
                    handle.write(CONFLICT + ANSWER if decided is True else decided)
                with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", "tests.md"), "w", encoding="utf-8") as handle:
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
        baseline = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".tests-baseline")
        with open(baseline, encoding="utf-8") as handle:
            text = re.sub(r"^[0-9a-f]{40}", "0" * 40, handle.read(), flags=re.M)
        with open(baseline, "w", encoding="utf-8") as handle:
            handle.write(text)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: a baseline blob that is gone is skipped and named, not passed in silence",
                             "gate:skip tests-kept" in output and "pruned" in output,
                             "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    with tmpdir() as root:
        # a test changed and committed after the baseline — by someone else: a run commits nothing mid-story
        build_project(root, extra_sources=((unit, old_test),))
        for command in (["init", "-q"], ["add", "-A"],
                        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        with open(os.path.join(root, unit), "w", encoding="utf-8") as handle:
            handle.write(changed_line(old_test))
        for command in (["add", unit], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "elsewhere"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: a test committed since the baseline changed outside the story and is not its",
                             verdict == "pass", "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    with tmpdir() as root:
        # the same commit made inside a stage's window is the stage's: held to the baseline
        build_project(root, extra_sources=((unit, old_test),))
        for command in (["init", "-q"], ["add", "-A"],
                        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        subprocess.run([sys.executable, args.cli, "--stage-start", "build", "--story", "STORY-1"], cwd=root,
                       capture_output=True, env=dict(os.environ, FACTORY_SESSION_USAGE="off"))
        with open(os.path.join(root, unit), "w", encoding="utf-8") as handle:
            handle.write(changed_line(old_test))
        for command in (["add", unit], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "by the stage"]):
            subprocess.run(["git", *command], cwd=root, capture_output=True)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: a test a stage changed and committed inside its window is still refused",
                             verdict == "fail", "; ".join(l for l in output.splitlines() if "tests-kept" in l)))
    with tmpdir() as root:
        build_project(root)
        verdict, output = kept_verdict(root)
        expectations.append(("tests-kept: outside a git repository the check is skipped and named",
                             verdict == "skip", verdict))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
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
                        story=delivered_story(STORY, "2026-09-23T00:00:00Z"),
                        extra_sources=((".dca-factory/runs/STORY-1/document.md", DOCUMENT),
                                       (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                       (".dca-factory/runs/STORY-3/plan.md", PLAN_ASKING.replace("STORY-1", "STORY-3")),
                                       ("project/epics/sample/STORY-3.decisions/01.md",
                                        DECISION.replace("STORY-1", "STORY-3"))))
        with open(os.path.join(root, "project", "epics", "sample", "STORY-7.md"), "w", encoding="utf-8") as handle:
            handle.write(story("STORY-7", status="draft"))
        with open(os.path.join(root, "project", "epics", "README.md"), "w", encoding="utf-8") as handle:
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
                        extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                       (".dca-factory/runs/STORY-1/tests.md", TESTS + "\n## needs-human\ndecision: STORY-1-01\n"),
                                       ("project/epics/sample/STORY-1.decisions/01.md",
                                        DECISION.replace("stage: plan", "stage: test"))))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a waiting story with code in the tree holds the checkout",
                             nxt.startswith("none") and "STORY-1 holds unfinished code" in nxt
                             and rows.get("STORY-2") == ("ready", "plan") and wait == "yes",
                             f"next: {nxt}"))
        with open(os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md"), "a",
                  encoding="utf-8") as handle:
            handle.write(ANSWER)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: once answered, the holder resumes at the stage that asked",
                             rows.get("STORY-1") == ("resumable", "test") and nxt == "STORY-1 test",
                             f"{rows.get('STORY-1')}, next: {nxt}"))
    with tmpdir() as root:
        backlog_project(root, extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                             (".dca-factory/runs/STORY-1/tests.md", TESTS),
                                             (".dca-factory/runs/STORY-1/build.md", "## Changed\n"),
                                             (".dca-factory/runs/STORY-1/.gate-build.txt", "gate:fail tests-green\n")))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a refused gate sends its story back to that stage",
                             rows.get("STORY-1") == ("in-progress", "build"), rows.get("STORY-1")))
        with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".rounds"), "w", encoding="utf-8") as handle:
            handle.write("3\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: three rounds stop the story, and nothing waits for them",
                             rows.get("STORY-1", ("",))[0] == "stopped" and nxt.startswith("none")
                             and wait == "no", f"{rows.get('STORY-1')}, next: {nxt}, wait: {wait}"))
    with tmpdir() as root:
        # the marks the gates leave: the plan gate records the story it let through, the document gate
        # that it passed — and the schedule reads both
        backlog_project(root, extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                             (".dca-factory/runs/STORY-1/tests.md", TESTS),
                                             (".dca-factory/runs/STORY-1/build.md", "# Build\n"),
                                             (".dca-factory/runs/STORY-1/tidy.md", "# Tidy\n"),
                                             (".dca-factory/runs/STORY-1/judge.md", "## Verdict\nverdict: pass\n"),
                                             (".dca-factory/runs/STORY-1/document.md", DOCUMENT)))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a document file without its gate's mark is not delivered",
                             rows.get("STORY-1") == ("in-progress", "document"), rows.get("STORY-1")))
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "document"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: the document gate's pass is what makes a story delivered",
                             rows.get("STORY-1") == ("delivered", None) and story_delivered(root),
                             rows.get("STORY-1")))
    with tmpdir() as root:
        backlog_project(root, extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),))
        subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        unchanged = rows.get("STORY-1")
        with open(os.path.join(root, "project", "epics", "sample", "STORY-1.md"), "a", encoding="utf-8") as handle:
            handle.write("- answered: archived things are hidden (the-expert, 2026-09-23).\n")
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a story edited after its plan runs from plan again",
                             unchanged == ("in-progress", "test") and rows.get("STORY-1") == ("in-progress", "plan")
                             and "the story changed after it was planned" in output,
                             f"before the edit {unchanged}, after {rows.get('STORY-1')}"))
    with tmpdir() as root, tmpdir() as home:
        # a story's last stages end its run, so no later stage of its own freezes their windows — the
        # next writing command does, for every story, once a window has settled
        backlog_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        session = "0e0e0e0e-aaaa-bbbb-cccc-343434343434"
        stamp = lambda ago: time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - ago))
        write_file(root, ".dca-factory/runs/STORY-1/.verify/journal.tsv",
                   f"{stamp(900)}\tusage\tdocument\ttool=claude-session\twindow={stamp(1200)}/{stamp(900)}"
                   f"\tsession=claude:{session}\n"
                   f"{stamp(60)}\tusage\tjudge\ttool=claude-session\twindow={stamp(120)}/{stamp(60)}"
                   f"\tsession=claude:{session}\n")
        write_file(home, f"projects/-any-project/{session}.jsonl", "".join(json.dumps({
            "timestamp": stamp(ago), "message": {"id": f"m{ago}", "model": "model-x", "usage": {
                "input_tokens": 7, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 10,
                "output_tokens": 5}}}) + "\n" for ago in (1000, 90)))
        env = dict(os.environ, CLAUDE_CONFIG_DIR=home)
        subprocess.run([sys.executable, args.cli, "--release", "nobody"], cwd=root, env=env, capture_output=True)
        journal = open(os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "journal.tsv"), encoding="utf-8").read()
        document_line = next((l for l in journal.splitlines() if "\tdocument\t" in l), "")
        judge_line = next((l for l in journal.splitlines() if "\tjudge\t" in l), "")
        expectations.append(("usage: a release freezes a story's settled last window into its journal, and "
                             "leaves a young one open",
                             "input=7" in document_line and "session=" not in document_line
                             and "session=" in judge_line and "input=" not in judge_line, journal))
    with tmpdir() as root, tmpdir() as home:
        # inside a stage the journal is silent; the stage's session log is where its sign of life is
        backlog_project(root)
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        session = "0f0f0f0f-aaaa-bbbb-cccc-121212121212"
        started = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 120))
        write_file(root, ".dca-factory/runs/STORY-1/.verify/journal.tsv", f"{started}\tstage-start\tbuild\ttool=claude-session\n")
        write_file(home, f"projects/-any-project/{session}.jsonl", json.dumps({"type": "assistant", "message": {
            "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "./gradlew test --rerun"}}]}}) + "\n")
        env = dict(os.environ, CLAUDE_CONFIG_DIR=home)
        subprocess.run([sys.executable, args.cli, "--claim", f"claude-session:{session}"], cwd=root, env=env,
                       capture_output=True)
        seen = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        expectations.append(("status: a running stage shows its session log's last activity and tool call",
                             re.search(r"activity: \d+ s ago — last tool call Bash: ./gradlew test --rerun", seen)
                             is not None, [l for l in seen.splitlines() if l.startswith(("activity", "worker"))]))
        off = subprocess.run([sys.executable, args.cli, "--status", "--live"], cwd=root,
                             env=dict(env, FACTORY_SESSION_USAGE="off"), capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
        expectations.append(("status: with session usage off the log is not read, and that is said",
                             "activity: not read" in off and "gradlew" not in off,
                             [l for l in off.splitlines() if l.startswith("activity")]))
    with tmpdir() as root, tmpdir() as home:
        # writing a story is measured like a stage, but it is not one: the story does not run, nothing waits
        backlog_project(root)
        session = "0d0d0d0d-aaaa-bbbb-cccc-565656565656"
        env = dict(os.environ, CLAUDE_CONFIG_DIR=home, CLAUDE_CODE_SESSION_ID=session)
        gate = lambda *more: subprocess.run([sys.executable, args.cli, *more], cwd=root, env=env,
                                            capture_output=True, text=True, encoding="utf-8")
        gate("--window-start", "backlog", "--story", "STORY-1")
        rows_during, _nxt, _wait, _ = schedule_of(args.gate, root)
        time.sleep(1.1)
        moment = datetime.now(timezone.utc) - timedelta(seconds=0.5)       # inside the window, to the millisecond
        stamp = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
        write_file(home, f"projects/-any/{session}.jsonl", json.dumps({"timestamp": stamp, "message": {
            "id": "w1", "model": "model-x", "usage": {"input_tokens": 5, "cache_read_input_tokens": 40,
                                                        "cache_creation_input_tokens": 50, "output_tokens": 5}}}) + "\n")
        gate("--window-end", "backlog", "--story", "STORY-1")
        detail = gate("--status", "--story", "STORY-1").stdout
        backlog_row = next((l for l in detail.splitlines() if l.strip().startswith("backlog")), "")
        expectations.append(("window: writing a story is measured — its own row, its tokens, what it was — and the "
                             "story is not running meanwhile",
                             rows_during.get("STORY-1", ("",))[0] != "running"
                             and re.search(r"backlog\s+1\s+\d+ s\s+5\s+5\s+50\s+40\s+100\s+writing the story",
                                           backlog_row) is not None, backlog_row or detail[-400:]))
        expectations.append(("window: a name that is not backlog or decisions is refused",
                             gate("--window-start", "judge", "--story", "STORY-1").returncode == 2, ""))
    with tmpdir() as root:
        # a shared builder that stopped on the plan's question, then ran again: the second window is the
        # question's, not a repeat a gate refused — the record names `stage: plan`, the window is `builder`
        build_project(root, **with_decisions(("STORY-1-01", DECISION + ANSWER)))
        write_file(root, ".dca-factory/runs/STORY-1/.verify/journal.tsv",
                   "2026-09-28T10:00:00.000Z\tstage-start\tbuilder\ttool=claude-session\n"
                   "2026-09-28T10:05:00.000Z\tstage-end\tbuilder\texit=0\n"
                   "2026-09-28T10:20:00.000Z\tstage-start\tbuilder\ttool=claude-session\n"
                   "2026-09-28T10:36:00.000Z\tstage-end\tbuilder\texit=0\n")
        detail = subprocess.run([sys.executable, args.cli, "--status", "--story", "STORY-1"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        builder_row = next((l for l in detail.splitlines() if l.strip().startswith("builder")), "")
        expectations.append(("status: a shared builder that stopped on a stage's question shows the question, "
                             "not `a gate refused`",
                             "1 question (STORY-1-01)" in builder_row and "a gate refused" not in builder_row,
                             builder_row or detail[-400:]))
    with tmpdir() as root:
        # a story delivered before the pipeline kept a journal says so once; a long answer wraps, whole
        long_question = "Does " + " ".join(["an archived entry"] * 12) + " count as the thing the reader sees?"
        backlog_project(root, ("STORY-2", []), story=delivered_story(STORY, "2026-09-20T10:00:00Z"), extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED), (".dca-factory/runs/STORY-1/tests.md", TESTS),
            (".dca-factory/runs/STORY-1/document.md", DOCUMENT),
            ("project/epics/sample/STORY-1.decisions/01.md", DECISION.replace(
                "# Does an archived thing count?", "# " + long_question) + ANSWER)))
        overview = subprocess.run([sys.executable, args.cli, "--status"], cwd=root, capture_output=True,
                                  text=True, encoding="utf-8").stdout
        detail = subprocess.run([sys.executable, args.cli, "--status", "--story", "STORY-1"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8").stdout
        row1 = next((l for l in overview.splitlines() if "STORY-1" in l and "delivered" in l), "")
        row2 = next((l for l in overview.splitlines() if "STORY-2" in l and "ready" in l), "")
        expectations.append(("status: a story delivered without a journal says so once; one not run yet does not",
                             "no journal" in row1 and "no journal" not in row2
                             and "delivered before the pipeline measured" in detail, row1 + "\n" + row2))
        expectations.append(("status: a long answer wraps inside its column and is never cut",
                             "…" not in detail and "count as the thing the reader sees?" in detail
                             and all(len(l) <= 120 for l in detail.splitlines()), detail[-600:]))
    with tmpdir() as root:
        # the observer reads the gate's own records the way the gate writes them: the red ledger as
        # `selector<TAB>digest`, the build's `## Changed` table with its paths in plain cells
        backlog_project(root, extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED), (".dca-factory/runs/STORY-1/tests.md", TESTS),
            (".dca-factory/runs/STORY-1/.tests-red", "".join(f"{sel}\t{'a' * 64}\n" for sel in both_green))))
        observed = subprocess.run([sys.executable, os.path.join(HERE, "observe.py"), "--story", "STORY-1",
                                   "--json"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
        try:
            held = [item["kind"] for item in json.loads(observed.stdout)["held"]]
        except (ValueError, KeyError):
            held = []
        expectations.append(("observe: a red ledger with digests counts every mapped test as recorded red",
                             "red-green" in held, observed.stdout.strip()[-300:]))
        spec = importlib.util.spec_from_file_location("factory_observe_tables", os.path.join(HERE, "observe.py"))
        observer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(observer)
        rows = observer.table_paths("## Changed\n| File | Why |\n| --- | --- |\n| src/main/App.java | why |\n"
                                    "| src/main/resources/app.properties | why |\n\n## Criteria\n| not/this.java | x |\n")
        expectations.append(("observe: the build table's plain paths are claims, any extension, only under `## Changed`",
                             "src/main/App.java" in rows and "src/main/resources/app.properties" in rows
                             and "not/this.java" not in rows, rows))
    # --- WP-66: acceptance before delivery --------------------------------
    def accept_fixture(root, profile_lines, *stories, extra=()):
        backlog_project(root, *stories, extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                                       (".dca-factory/runs/STORY-1/tests.md", TESTS),
                                                       (".dca-factory/runs/STORY-1/build.md", "# Build\n"),
                                                       (".dca-factory/runs/STORY-1/tidy.md", "# Tidy\n"),
                                                       (".dca-factory/runs/STORY-1/judge.md", "## Verdict\nverdict: pass\n"),
                                                       (".dca-factory/runs/STORY-1/document.md", DOCUMENT)) + tuple(extra))
        with open(os.path.join(root, "dca-factory.profile.yaml"), "a", encoding="utf-8") as h:
            h.write(profile_lines)

    def gate_run(root, *argv):
        return subprocess.run([sys.executable, args.gate] + list(argv), cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def cli_run(root, *argv):
        return subprocess.run([sys.executable, args.cli] + list(argv), cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def answer(root, rid, text):
        with open(os.path.join(root, record_file(rid)), "a", encoding="utf-8") as h:
            h.write(f"\n## Answer\nanswer: {text}\nby: a-human\nat: 2026-09-25T15:00:00Z\n")

    story_file = lambda root: os.path.join(root, "project", "epics", "sample", "STORY-1.md")
    delivered = lambda root: story_delivered(root)
    record = lambda root, n: os.path.join(root, record_file(f"STORY-1-accept-{n}"))

    with tmpdir() as root:
        accept_fixture(root, "acceptance: all\n", ("STORY-2", []))
        asked = gate_run(root, "--story", "STORY-1", "--stage", "document")
        rows, nxt, wait, _ = schedule_of(args.gate, root)
        expectations.append(("acceptance: the document gate asks instead of delivering — exit 3, a record, the story "
                             "waits and holds the checkout",
                             asked.returncode == 3 and not delivered(root) and os.path.isfile(record(root, 1))
                             and "kind: acceptance" in open(record(root, 1), encoding="utf-8").read()
                             and rows.get("STORY-1", ("",))[0] == "waiting" and nxt.startswith("none"),
                             f"exit {asked.returncode}; {rows.get('STORY-1')}; next: {nxt}"))
        answer(root, "STORY-1-accept-1", "accepted")
        rows, _n, _w, _ = schedule_of(args.gate, root)
        given = gate_run(root, "--story", "STORY-1", "--stage", "document")
        expectations.append(("acceptance: accepted — the schedule sends it to the document gate, which delivers",
                             rows.get("STORY-1") == ("resumable", "document") and given.returncode == 0
                             and delivered(root), f"{rows.get('STORY-1')}; exit {given.returncode}"))

    with tmpdir() as root:
        accept_fixture(root, "acceptance: all\n")
        gate_run(root, "--story", "STORY-1", "--stage", "document")
        answer(root, "STORY-1-accept-1", "correction: two cards on m")
        pending = gate_run(root, "--story", "STORY-1", "--stage", "document")
        with open(story_file(root), "a", encoding="utf-8") as h:
            h.write("- answered: two cards on m (a-human, STORY-1-accept-1).\n")
        gate_run(root, "--story", "STORY-1", "--stage", "plan")        # the digest of the story as planned
        with open(story_file(root), "a", encoding="utf-8") as h:
            h.write("- answered: and the buttons stay (a-human, STORY-1-accept-1).\n")
        rows, _n, _w, _ = schedule_of(args.gate, root)
        expectations.append(("acceptance: a correction not yet in the story fails the gate; written in, the same "
                             "story runs again from plan",
                             pending.returncode == 1 and "correction that is not in the story" in pending.stdout
                             and rows.get("STORY-1") == ("in-progress", "plan") and not delivered(root),
                             f"exit {pending.returncode}; {rows.get('STORY-1')}"))
        gate_run(root, "--story", "STORY-1", "--stage", "plan")        # the correction ran: planned again
        asked_again = gate_run(root, "--story", "STORY-1", "--stage", "document")
        expectations.append(("acceptance: after the correction ran, the story is asked again, in a record of its own",
                             asked_again.returncode == 3 and os.path.isfile(record(root, 2)),
                             asked_again.stdout.strip()[-200:]))

    with tmpdir() as root:
        accept_fixture(root, "acceptance: pages\n")
        given = gate_run(root, "--story", "STORY-1", "--stage", "document")
        expectations.append(("acceptance: pages — a project without a browser delivers without asking",
                             given.returncode == 0 and delivered(root), given.stdout.strip()[-200:]))

    with tmpdir() as root:
        accept_fixture(root, "acceptance: pages\nbrowser: playwright\ne2eTest: ./gradlew test-pages\n",
                       extra=(("src/test-pages/java/com/example/WidgetPageTest.java",
                               "class WidgetPageTest {\n  void showsTheThing() {}\n}\n"),
                              ("src/test/java/com/example/WidgetUnitTest.java",
                               "class WidgetUnitTest {\n  void showsNothingWhenEmpty() {}\n}\n")))
        asked = gate_run(root, "--story", "STORY-1", "--stage", "document")
        expectations.append(("acceptance: pages — a story whose test the end-user command runs waits for a human",
                             asked.returncode == 3 and not delivered(root), asked.stdout.strip()[-200:]))

    with tmpdir() as root:
        accept_fixture(root, "")
        gate_run(root, "--story", "STORY-1", "--stage", "plan")
        gate_run(root, "--story", "STORY-1", "--stage", "document")
        refused = cli_run(root, "--reopen", "STORY-1")
        write_file(root, "project/epics/sample/STORY-1.decisions/accept-1.md",
                   "---\nid: STORY-1-accept-1\nstory: STORY-1\nstage: document\nkind: acceptance\n"
                   "asked: 2026-09-25T15:00:00Z\ndigest: none\n---\n\n# Accept STORY-1?\n")
        answer(root, "STORY-1-accept-1", "correction: eight products")
        uncited = cli_run(root, "--reopen", "STORY-1")
        with open(story_file(root), "a", encoding="utf-8") as h:
            h.write("- answered: eight products (a-human, STORY-1-accept-1).\n")
        taken = cli_run(root, "--reopen", "STORY-1")
        rows, _n, _w, _ = schedule_of(args.gate, root)
        first_pass = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".verify", "pass-1")
        kept = os.path.isfile(os.path.join(first_pass, "document.md")) and os.path.isfile(os.path.join(first_pass, "plan.md")) \
            and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "STORY-1", "plan.md"))
        expectations.append(("reopen: only with an answered correction the story cites; then the story no longer says "
                             "delivered, the delivered pass is kept as pass-1, and the same story runs from plan",
                             refused.returncode == 1 and uncited.returncode == 1 and taken.returncode == 0
                             and not delivered(root) and kept and rows.get("STORY-1") == ("ready", "plan")
                             and "pass-1" in taken.stdout,
                             f"{refused.returncode}/{uncited.returncode}/{taken.returncode}; {rows.get('STORY-1')}; "
                             f"kept {kept}; {taken.stdout.strip()[-200:]}"))

    with tmpdir() as root:
        accept_fixture(root, "", ("STORY-2", []), extra=((".dca-factory/runs/STORY-2/plan.md", PLAN_APPLIED),
                                                         (".dca-factory/runs/STORY-2/tests.md", TESTS)))
        gate_run(root, "--story", "STORY-1", "--stage", "document")
        write_file(root, "project/epics/sample/STORY-1.decisions/accept-1.md",
                   "---\nid: STORY-1-accept-1\nstory: STORY-1\nstage: document\nkind: acceptance\n"
                   "asked: 2026-09-25T15:00:00Z\ndigest: none\n---\n\n# Accept STORY-1?\n")
        answer(root, "STORY-1-accept-1", "correction: eight products")
        with open(story_file(root), "a", encoding="utf-8") as h:
            h.write("- answered: eight products (a-human, STORY-1-accept-1).\n")
        held = cli_run(root, "--reopen", "STORY-1")
        expectations.append(("reopen: refused while another story holds the checkout with unfinished code",
                             held.returncode == 1 and "STORY-2 holds the checkout" in held.stdout and delivered(root),
                             held.stdout.strip()[-200:]))

    with tmpdir() as root:
        accept_fixture(root, "acceptance: all\n")
        gate_run(root, "--story", "STORY-1", "--stage", "plan")
        gate_run(root, "--story", "STORY-1", "--stage", "document")
        answer(root, "STORY-1-accept-1", "accepted")
        gate_run(root, "--story", "STORY-1", "--stage", "document")
        text = open(story_file(root), encoding="utf-8").read()
        write_file(root, "project/epics/sample/STORY-1.md",
                   text.replace("The reader sees the thing.", "The reader sees two things.")
                   + "- answered: two things (a-human, STORY-1-accept-2).\n")
        write_file(root, "project/epics/sample/STORY-1.decisions/accept-2.md",
                   "---\nid: STORY-1-accept-2\nstory: STORY-1\nstage: document\nkind: acceptance\n"
                   "asked: 2026-09-25T16:00:00Z\ndigest: none\n---\n\n# Accept STORY-1?\n")
        answer(root, "STORY-1-accept-2", "correction: two things")
        wish = cli_run(root, "--reopen", "STORY-1")
        expectations.append(("reopen: after an acceptance, a changed criterion is a new wish, not a reopened story",
                             wish.returncode == 1 and "new wish" in wish.stdout and delivered(root),
                             wish.stdout.strip()[-200:]))

    with tmpdir() as root:
        # the backlog skill checks one story while it is still being written: the plan gate's checks,
        # none of its marks — a baseline taken then would be the wrong one, and the files it leaves
        # under tasks/ make the commit hook refuse the backlog commit
        backlog_project(root, ("STORY-2", []))
        one = subprocess.run([sys.executable, args.gate, "--check-backlog", "--story", "STORY-1"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        missing = subprocess.run([sys.executable, args.gate, "--check-backlog", "--story", "STORY-9"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        expectations.append(("backlog check: one story is checked, and nothing is written under tasks/",
                             one.returncode == 0 and "1 story(ies) checked" in one.stdout
                             and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "STORY-1")),
                             one.stdout.strip()[-200:]))
        expectations.append(("backlog check: a story that is not there is refused, not passed as empty",
                             missing.returncode == 1 and "no story STORY-9" in missing.stdout,
                             missing.stdout.strip()[-200:]))
    with tmpdir() as root:
        # a judge's story conflict: waits, resumes where the answer lands, then runs the rest again
        backlog_project(root, extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED), (".dca-factory/runs/STORY-1/tests.md", TESTS),
            (".dca-factory/runs/STORY-1/build.md", "## Changed\n"), (".dca-factory/runs/STORY-1/tidy.md", "## Moves\n"),
            (".dca-factory/runs/STORY-1/judge.md", JUDGE_CONFLICT),
            ("project/epics/sample/STORY-1.decisions/01.md", CONFLICT)))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        waiting = rows.get("STORY-1")
        record = os.path.join(root, "project", "epics", "sample", "STORY-1.decisions", "01.md")
        with open(record, "a", encoding="utf-8") as handle:
            handle.write(ANSWER)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        resumable = rows.get("STORY-1")
        with open(os.path.join(root, ".dca-factory", "runs", "STORY-1", "tests.md"), "w", encoding="utf-8") as handle:
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
        backlog_project(root, ("STORY-2", []), extra_sources=((".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED),
                                                             (".dca-factory/runs/STORY-1/tests.md", TESTS)))
        path = os.path.join(root, "project", "epics", "sample", "STORY-1.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("status: approved", "status: superseded")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a superseded story holds the checkout for nobody, tests or not",
                             rows.get("STORY-1", ("",))[0] == "superseded" and nxt == "STORY-2 plan", f"next: {nxt}"))
    with tmpdir() as root:
        backlog_project(root, extra_sources=((".dca-factory/runs/STORY-1/.gate-plan.txt", "gate:fail epic\n"),))
        refused = os.path.join(root, ".dca-factory", "runs", "STORY-1", ".gate-plan.txt")
        os.utime(refused, (time.time() - 60, time.time() - 60))
        story_file = os.path.join(root, "project", "epics", "sample", "STORY-1.md")
        for name in ("STORY-1.md", "epic.md"):
            os.utime(os.path.join(root, "project", "epics", "sample", name), (time.time() - 120, time.time() - 120))
        rows, nxt, wait, output = schedule_of(args.gate, root)
        stopped = rows.get("STORY-1")
        os.utime(story_file, None)                              # repaired after the refusal
        rows, nxt, wait, output = schedule_of(args.gate, root)
        expectations.append(("schedule: a story the plan gate refused runs from plan again once it was repaired",
                             stopped[0] == "stopped" and rows.get("STORY-1") == ("in-progress", "plan"),
                             f"before {stopped}, after {rows.get('STORY-1')}"))
    with tmpdir() as root:
        os.makedirs(os.path.join(root, ".dca-factory", "runs", "S-1", ".verify"))
        journal = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "journal.tsv")
        line = "2026-01-01T00:00:00Z\tusage\tbuild\ttool=claude-session\twindow=2026-01-01T00:00:00Z/2026-01-01T00:01:00Z\tsession=claude:abc\n"
        write_file(root, ".dca-factory/runs/S-1/.verify/journal.tsv", "2026-01-01T00:00:00Z\tstage-start\tbuild\ttool=claude-session\n" + line)
        before = open(journal, encoding="utf-8").read()
        home = os.path.join(root, "home")
        write_file(home, "projects/p/abc.jsonl", json.dumps({"timestamp": "2026-01-01T00:00:30Z", "type": "assistant",
                   "message": {"id": "m1", "model": "x", "usage": {"input_tokens": 5, "output_tokens": 7}}}) + "\n")
        subprocess.run([sys.executable, args.cli, "--usage"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", env=dict(os.environ, CLAUDE_CONFIG_DIR=home))
        expectations.append(("usage: `--usage` only reads — the journal is not rewritten",
                             open(journal, encoding="utf-8").read() == before, ""))
    with tmpdir() as root:
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        write_file(root, ".git/dca-factory-worker.lock", "")
        taken = subprocess.run([sys.executable, args.cli, "--claim", "someone"], cwd=root, capture_output=True,
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
        os.makedirs(os.path.join(root, ".dca-factory", "runs", "S-1"), exist_ok=True)
        with open(os.path.join(root, ".dca-factory", "runs", "S-1", "build.md"), "w", encoding="utf-8") as handle:
            handle.write("## Files\n")                      # a run artefact: never part of the change
        mark("end")
        folder = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify")
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
    rows_of = lambda cwd, name: sorted(open(os.path.join(cwd, ".dca-factory", "runs", "S-1", ".verify", name),
                                            encoding="utf-8").read().splitlines()) \
        if os.path.isfile(os.path.join(cwd, ".dca-factory", "runs", "S-1", ".verify", name)) else []
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
        diff = open(os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "story.diff"), encoding="utf-8").read()
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
        diff = open(os.path.join(project, ".dca-factory", "runs", "S-1", ".verify", "story.diff"), encoding="utf-8").read()
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
        diff = os.path.join(root, ".dca-factory", "runs", "S-1", ".verify", "story.diff")
        expectations.append(("changes: outside a repository there is no diff, and the file says so",
                             os.path.isfile(diff) and "no diff" in open(diff, encoding="utf-8").read(), ""))

    with tmpdir() as root:
        write_file(root, ".dca-factory/runs/S-1/judge.md", "## Verdict\nverdict: changes-requested\n")
        started = subprocess.run([sys.executable, args.cli, "--stage-start", "judge", "--story", "S-1"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8",
                                 env=dict(os.environ, FACTORY_SESSION_USAGE="off"))
        expectations.append(("judge: in a session, the repeat round's stage mark moves the verdict before it aside",
                             os.path.isfile(os.path.join(root, ".dca-factory", "runs", "S-1", ".judge-previous.md"))
                             and not os.path.exists(os.path.join(root, ".dca-factory", "runs", "S-1", "judge.md"))
                             and ".judge-previous.md" in started.stdout, started.stdout.strip()))
    # --- the project description before the first story, checked without a story -------------------
    with tmpdir() as root:
        check = lambda: subprocess.run([sys.executable, args.gate, "--project"], cwd=root,
                                       capture_output=True, text=True, encoding="utf-8")
        none = check()
        write_file(root, "project/product.md", PRODUCT)
        only_product = check()
        write_file(root, "project/tech.md", TECH.replace("## Runtime\n\nA container.\n", "## Runtime\n\n"))
        incomplete = check()
        write_file(root, "project/tech.md", TECH)
        complete = check()
        expectations.append(("project: `--project` exits 3 while a part is missing, 1 when a heading is empty, 0 "
                             "when both stand", (none.returncode, only_product.returncode, incomplete.returncode,
                                                 complete.returncode) == (3, 3, 1, 0)
                             and "/factory-setup" in none.stdout,
                             f"exits {none.returncode}/{only_product.returncode}/{incomplete.returncode}/"
                             f"{complete.returncode}; {none.stdout.strip()}"))
    with tmpdir() as root:
        # the layout before `project/`: named with the move, never read
        write_file(root, "backlog/product.md", PRODUCT)
        write_file(root, "backlog/sample/epic.md", EPIC)
        write_file(root, "backlog/sample/STORY-1.md", STORY)
        write_file(root, "dca-factory.profile.yaml", PROFILE)
        brief = subprocess.run([sys.executable, args.cli, "--status", "--brief"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8").stdout
        planned = subprocess.run([sys.executable, args.gate, "--story", "STORY-1", "--stage", "plan"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("layout: a backlog at the project root is named with the move to project/, and not read",
                             "backlog/ at the root is now project/epics/" in brief and "backlog/product.md" in brief
                             and "backlog/ at the root is now project/epics/" in planned and "gate:fail layout" in planned
                             and "no story 'STORY-1' under project/epics" in planned,
                             f"{brief.strip()} | {planned.strip()[-200:]}"))
    with tmpdir() as root:
        backlog_project(root, extra_sources=(("project/epics/sample/STORY-2.md",
                                               story("STORY-2").replace(" (happy path):", ":")),))
        checked = subprocess.run([sys.executable, args.gate, "--check-backlog"], cwd=root, capture_output=True,
                                 text=True, encoding="utf-8").stdout
        expectations.append(("check-backlog: a story without a happy path is named, as the plan gate would",
                             "happy-path" in checked and "STORY-2" in checked and "0 scenarios marked" in checked,
                             checked[-500:]))
    with tmpdir() as root:
        # an adopted story: to adopt, then delivered (adopted); a story depending on it waits for the adoption
        backlog_project(root, ("STORY-2", ["STORY-1"]),
                        story=STORY.replace("status: approved", "status: adopted"))
        first = subprocess.run([sys.executable, args.cli, "--status", "--part", "backlog"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8").stdout
        rows, _n, _w, listing = schedule_of(args.gate, root)
        write_file(root, ".dca-factory/runs/STORY-1/judge.md", "verdict: pass\n")
        judged = schedule_of(args.gate, root)[0]
        mark_delivered(root, "STORY-1")
        after = subprocess.run([sys.executable, args.cli, "--status", "--part", "backlog"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("adopt: an adopted story reads 'to adopt', and a story depending on it waits for the adoption",
                             "to adopt" in first and rows.get("STORY-2", ("", ""))[0] == "blocked", listing))
        expectations.append(("adopt: after the judge's pass only the adopt gate is left",
                             judged.get("STORY-1", ("", ""))[1] == "adopt", judged))
        expectations.append(("adopt: once adopted it reads 'delivered (adopted)'", "delivered (adopted)" in after,
                             after[-500:]))
        expectations.append(("status: an adopted story counts as delivered in its epic's header",
                             "1 of 2 delivered" in after, after[-500:]))
    with tmpdir() as root:
        # a killed runner leaves a stage-start without an end; a delivered story stays delivered, not running
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        backlog_project(root, story=delivered_story(STORY),
                        extra_sources=((".dca-factory/runs/STORY-1/document.md", "# Document\n"),
                                             (".dca-factory/runs/STORY-1/.verify/journal.tsv",
                                              f"{started}\tstage-start\ttidy\ttool=claude\n")))
        rows, nxt, _w, listing = schedule_of(args.gate, root)
        shown = subprocess.run([sys.executable, args.cli, "--status"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8").stdout
        expectations.append(("schedule: a delivered story with an open stage in its journal is delivered, not running",
                             rows.get("STORY-1", ("", ""))[0] == "delivered" and "Nothing is running." in shown
                             and "1 of 1 delivered" in shown, listing + shown[-400:]))
    with tmpdir() as root:
        # `--start`: where `run --story` begins without --from — the story's state, never plan by default
        backlog_project(root, ("STORY-2", ["STORY-1"]), extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", "# Plan\n"), (".dca-factory/runs/STORY-1/tests.md", TESTS)))
        start_of = lambda sid: subprocess.run([sys.executable, args.cli, "--story", sid, "--start"], cwd=root,
                                              capture_output=True, text=True, encoding="utf-8")
        one, two, unknown = start_of("STORY-1"), start_of("STORY-2"), start_of("STORY-9")
        expectations.append(("start: a story with plan and tests written starts at build",
                             "state: in-progress" in one.stdout and "start: build" in one.stdout, one.stdout))
        expectations.append(("start: a story whose dependency is not delivered starts nowhere, and says why",
                             "state: blocked" in two.stdout and "start: none" in two.stdout
                             and "STORY-1" in two.stdout, two.stdout))
        expectations.append(("start: an unknown story is refused (exit 2)", unknown.returncode == 2,
                             unknown.stdout + unknown.stderr))
    for label, older, newer, want in (
            # a story planned again — its text changed, a correction, a story conflict — runs every stage after
            ("a re-planned story resumes after its new plan, not at an earlier pass's document",
             ("tests.md", "build.md", "tidy.md", "judge.md", "document.md"), ("plan.md",), "test"),
            ("`changes-requested` over an earlier pass's document resumes at build",
             ("plan.md", "tests.md", "build.md", "tidy.md", "document.md"), ("judge.md",), "build"),
            ("a build run again after `changes-requested` resumes at tidy, not at build once more",
             ("plan.md", "tests.md", "tidy.md", "judge.md"), ("build.md",), "tidy")):
        with tmpdir() as root:
            files = {"plan.md": "# Plan\n", "tests.md": TESTS, "build.md": "# Build\n", "tidy.md": "# Tidy\n",
                     "judge.md": "## Verdict\nverdict: " + ("changes-requested" if "judge.md" in newer
                                                             or "changes" in label else "pass") + "\n",
                     "document.md": "# Document\n"}
            backlog_project(root, extra_sources=tuple((f".dca-factory/runs/STORY-1/{n}", files[n]) for n in older + newer))
            for number, name in enumerate(older):
                os.utime(os.path.join(root, ".dca-factory", "runs", "STORY-1", name), (1000 + number, 1000 + number))
            start = subprocess.run([sys.executable, args.cli, "--story", "STORY-1", "--start"], cwd=root,
                                   capture_output=True, text=True, encoding="utf-8").stdout
            expectations.append((f"start: {label}", f"start: {want}" in start, start))
    with tmpdir() as root:
        # in git, the scratch copy is what git sees — a package named `tasks` comes along
        build_project(root, story=ADOPTED, profile=PACKAGED_PROFILE, tests=TESTS + CHARACTERIZED,
                      extra_sources=PACKAGED_SOURCES)
        write_file(root, ".gitignore", "build/\n")
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
        code, output = run_gate(args.gate, root, "adopt")
        expectations.append(("adopt: in git, a break that changes nothing is refused where the code sits in a "
                             "package named `tasks`", code == 1 and "stays green under its break" in output,
                             output[-500:]))
    with tmpdir() as root:
        # a program missing on the PATH is the environment, not the story
        build_project(root, profile=PROFILE.replace("compile: true", "compile: dca-no-such-tool --version"))
        code, output = run_gate(args.gate, root, "test")
        expectations.append(("environment: a command whose program is not on the PATH fails as `environment`, named",
                             code != 0 and "environment" in checks_by_verdict(output)["fail"]
                             and "dca-no-such-tool" in output, output[-600:]))
    with tmpdir() as root:
        # a refusal left from an earlier round does not undo a delivery
        backlog_project(root, story=delivered_story(STORY),
                        extra_sources=((".dca-factory/runs/STORY-1/document.md", "# Document\n"),
                                       (".dca-factory/runs/STORY-1/.gate-plan.txt", "gate:fail decisions — stale\n")))
        rows = schedule_of(args.gate, root)[0]
        expectations.append(("schedule: a delivered story stays delivered when an earlier round left a refusal behind",
                             rows.get("STORY-1", ("", ""))[0] == "delivered", rows))
    with tmpdir() as root:
        # an answer that changes a test resumes at the test stage, whichever stage asked
        backlog_project(root, extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_APPLIED), (".dca-factory/runs/STORY-1/tests.md", TESTS),
            (".dca-factory/runs/STORY-1/build.md", "# Build\n\n## needs-human\ndecision: STORY-1-01\n"),
            ("project/epics/sample/STORY-1.decisions/01.md", CONFLICT.replace("stage: test", "stage: build")
             + ANSWER.replace("answer: b\n", "answer: b\napplies: test\n"))))
        rows = schedule_of(args.gate, root)[0]
        expectations.append(("decisions: an answer that says `applies: test` resumes the story at the test stage",
                             rows.get("STORY-1", ("", ""))[1] == "test", rows))
    with tmpdir() as root:
        # the plan asked, the answer changes a test: the plan runs again first and lists the tests that change
        backlog_project(root, extra_sources=(
            (".dca-factory/runs/STORY-1/plan.md", PLAN_ASKING),
            ("project/epics/sample/STORY-1.decisions/01.md", CONFLICT.replace("stage: test", "stage: plan")
             + ANSWER.replace("answer: b\n", "answer: b\napplies: test\n"))))
        rows = schedule_of(args.gate, root)[0]
        expectations.append(("decisions: a plan's question answered `applies: test` re-plans before the test stage",
                             rows.get("STORY-1", ("", ""))[1] == "plan", rows))
    with tmpdir() as root:
        # a journey: after its test it goes to the judge, and an epic delivered with an open journey is named
        journey = (story("JOURNEY-1", ("STORY-1",)).replace("status: approved\n", "status: approved\nkind: journey\n")
                   .replace(" (happy path):", ":"))
        backlog_project(root, epic=EPIC + "\n## Journey\n\n- open: which flow must never break\n",
                        story=delivered_story(STORY), extra_sources=(
            ("project/epics/sample/JOURNEY-1.md", journey),
            (".dca-factory/runs/STORY-1/document.md", "# Document\n"),
            (".dca-factory/runs/JOURNEY-1/plan.md", "# Plan\n"), (".dca-factory/runs/JOURNEY-1/tests.md", "# Tests\n")))
        rows, _nxt, _wait, listing = schedule_of(args.gate, root)
        expectations.append(("schedule: a journey whose test is written goes to the judge — no build, no tidy",
                             rows.get("JOURNEY-1", ("", ""))[1] == "judge", listing))
    with tmpdir() as root:
        backlog_project(root, epic=EPIC + "\n## Journey\n\n- open: which flow must never break\n",
                        story=delivered_story(STORY), extra_sources=((".dca-factory/runs/STORY-1/document.md", "# Document\n"),))
        view = subprocess.run([sys.executable, args.cli, "--status", "--part", "backlog"], cwd=root,
                              capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("status: an epic delivered with its journey still open is named, with the skill",
                             "journey   sample: every story is delivered and its journey is still open — /factory-backlog"
                             in view, view[-600:]))
    with tmpdir() as root:
        # before anything is there: the runner's help explains the factory from the plugin's gate
        shown = subprocess.run([BASH, args.runner, "help", "--format", "json"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8")
        try:
            fresh = json.loads(shown.stdout)
        except ValueError:
            fresh = {}
        expectations.append(("help: works before the pipeline is installed, the first step marked next",
                             shown.returncode == 0 and fresh
                             and [f["mark"] for f in fresh["flow"]] == ["next"] + ["none"] * 4
                             and fresh["next"]["action"]["skill"] == "/dca-new project"
                             and [f["number"] for f in fresh["flow"]] == [1, 2, 3, 4, 5]
                             and {f["step"]: f["shell"] for f in fresh["flow"]}["set up"] == "setup",
                             f"exit {shown.returncode}; {shown.stdout[:200]} {shown.stderr[:200]}"))
    with tmpdir() as root:
        build_project(root)
        brief = subprocess.run([sys.executable, args.cli, "--status", "--brief"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("status: the brief names a missing project description with /factory-setup",
                             "no project description" in brief and "/factory-setup" in brief, brief.strip()))
        write_file(root, "project/product.md", PRODUCT)
        write_file(root, "project/tech.md", TECH)
        shutil.rmtree(os.path.join(root, "project", "epics"))
        brief = subprocess.run([sys.executable, args.cli, "--status", "--brief"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8").stdout
        expectations.append(("status: the brief names an empty backlog with /factory-backlog",
                             "backlog is empty" in brief and "/factory-backlog" in brief, brief.strip()))
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
    # the skills call only the runner's verbs, which mirror them (WP-62 item 11)
    verbs = {"setup", "backlog", "run", "status", "decisions", "help", "update", "verify", "check"}
    called = []
    for folder, _, names in os.walk(skills_root):
        for name in names:
            if name.endswith((".md", ".tmpl")):
                path = os.path.join(folder, name)
                for number, line in enumerate(open(path, encoding="utf-8"), 1):
                    for verb in re.findall(r"factory\.sh\s+([a-z][a-z-]*)", line):
                        if verb not in verbs:
                            called.append(f"{os.path.relpath(path, skills_root)}:{number} {verb}")
    expectations.append(("verbs: every `factory.sh <verb>` a skill, reference or template names exists",
                         not called, ", ".join(called[:5])))
    backlog_skill = open(os.path.join(skills_root, "factory-backlog", "SKILL.md"), encoding="utf-8").read()
    expectations.append(("backlog: the question pass reads the three description files and asks about the "
                         "context, the surface and the technical fit",
                         all(w in backlog_skill for w in ("--project", "three files of the", "technical fit",
                                                          "designed map", "/factory-setup")), ""))
    for name, ok, detail in expectations:
        print(f"  {'ok   ' if ok else 'FAIL '} {name}")
        note_result(name, ok, detail)
        if not ok:
            print(f"          {detail}")
            schedule_failures.append(name)
    failures += [(name, [], "") for name in schedule_failures]

    return run_runner_groups(args, failures, "all" if args.group == "all" else "checks")


def run_runner_groups(args, failures, group):
    runner_failures = []
    if group == "checks":
        pass
    elif os.path.isfile(args.runner):
        if group in ("all", "runner"):
            print()
            CURRENT_GROUP[0] = "runner"
            runner_failures = verify_runner(args.runner, args.verbose)
        if group in ("all", "setup"):
            print()
            CURRENT_GROUP[0] = "setup"
            runner_failures += verify_setup(args.runner, args.verbose)
    else:
        print(f"verify: no runner at {args.runner} — its cases were skipped")

    if failures or runner_failures:
        print(f"\nverify: FAILED — {len(failures)} gate case(s), {len(runner_failures)} runner case(s)")
        return 1
    print("\nverify: the factory behaves as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
