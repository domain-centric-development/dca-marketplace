#!/usr/bin/env python3
"""Story gate — the deterministic part of a factory run.

Reads the backlog (markdown with front matter) and the stack profile, then checks
what a stage may not decide for itself. Exit code 0 means the stage may proceed.

    story-gate.py --story <id> --stage <plan|test|build|tidy|document> [options]
    story-gate.py --list-decisions [--story <id>]      the decision inbox, one line per record
    story-gate.py --schedule                           every story's state and the next one to run
    story-gate.py --change [--staged] [--checks <c>]   the profile's checks outside a story; --staged
                                                       checks what the commit contains (the hook, CI)
    story-gate.py --parity <config>                    every implementation's reports prove every
                                                       mandatory scenario of a scenario contract

Options:
    --backlog <dir>     backlog root (default: backlog)
    --tasks <dir>       run artefact root (default: tasks)
    --profile <file>    stack profile (default: .agents/factory/factory.profile.yaml,
                        falling back to factory.profile.yaml in the project root)
    --json              additionally print the result as one JSON object

Checks by stage:
    plan   epic completeness (intent, goal, metric, domain_contact), story well-formed and not
           left in draft, its bounded context present in the context map, the round limit not
           reached, and a note when the project instructions are too large for a tool to load
    test   epic + every acceptance criterion mapped to a test in tasks/<story>/tests.md,
           the test exists in the sources, the test sources compile, every mapped test is red.
           Which selectors were red is recorded in tasks/<story>/.tests-red
    build  epic + mapping + every mapped test is green **and was recorded red by the test stage**,
           every test command the profile's `required:` names, run whole (the stories before this
           one still hold), plus every extra check the profile declares for this stage
           (architecture suite, formatter, …). Without the record the green run is skipped and named, never taken as
           evidence: a runner that matched no test at all exits 0 exactly like a passing one
    tidy   the same as build: nothing the refactor touched may have changed what the code does
    document  every path, file and identifier the document stage claims actually exists, every
           row of its glossary table names where its definition came from, and every term the plan
           proposed has landed in a glossary
    change the profile's compile, test, architecture and format commands against the working tree
           (or, with --staged, the Git index — refused when the working tree differs from it). A test
           command passes only when its reports show executed cases. The profile's `required:` line
           makes checks mandatory: a required check that is not declared, not run or ran nothing fails
    every stage  the story's decision records under .agents/factory/decisions/: a `## needs-human`
           section names one, an open one stops the story, an answered one is applied by the
           stage that asked and then stamped `## Applied` here

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import json
import os
import re
import glob
import hashlib
import shutil
import subprocess
import sys
import time
from xml.etree import ElementTree

# The reports use `—` and `→`. A Windows console decodes stdout as cp1252 and a Python that
# inherits that raises on the first arrow; the files this writes are UTF-8 in every other respect,
# so the streams are too.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

EPIC_FIELDS = ("intent", "goal", "metric", "domain_contact")
MAX_ROUNDS = 3
#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools
#: have comparable budgets. Reported as a note, never a failure — the size is not this story's fault.
DOC_BUDGET_BYTES = 32 * 1024
CONTEXT_MAP_CANDIDATES = (
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)\s*:\s*(\S.*)$")
MAPPING_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|")
SELECTOR = re.compile(r"^([\w.]+)#([\w]+)$")

#: Two different questions, so two different numbers.
#:
#: CONTRACT is the version of the *files* the gate reads and writes: the stack profile's keys, the
#: `gate:tests` table, the red ledger, the shape of a document claim. It goes up only when an older
#: or newer artefact would be read wrongly — that is what makes a mismatch a refusal.
#:
#: VERSION is where this copy came from. The gate is *copied* into a project (`.agents/factory/`),
#: so a project can be governed by a release older than the pipeline it was installed from without
#: anything being incompatible. That is an update to offer, never a reason to refuse, and only the
#: installer can see it — it is the one place that holds both files.
CONTRACT = 3
VERSION = "0.9.1"


# --- tiny readers (no third-party dependencies) ------------------------------

def read_front_matter(path):
    """Return (front_matter_dict, body). Values are strings or lists of strings.

    Supports the flat subset the backlog contract prescribes: `key: value` and
    `key:` followed by `- item` lines. Nothing else is interpreted.
    """
    text = read_text(path)
    if not text.startswith("---"):
        raise GateError(f"{path}: no front matter (the file must start with ---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise GateError(f"{path}: front matter is not closed by ---")
    data, key = {}, None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("-", " ", "\t")) and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(line.strip()[1:].strip() if line.strip().startswith("-") else line.strip())
            continue
        if ":" not in line:
            raise GateError(f"{path}: cannot read front-matter line {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        data[key] = value if value else []
    return data, parts[2]


def read_profile(path):
    """Flat `key: value` profile. Missing file is not an error — every command
    is then reported as not declared."""
    if not path or not os.path.isfile(path):
        return {}
    profile = {}
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        profile[key.strip()] = value.strip().strip('"').strip("'")
    return profile


def read_text(path):
    if not os.path.isfile(path):
        raise GateError(f"{path}: file not found")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class GateError(Exception):
    pass


# --- backlog ----------------------------------------------------------------

def find_story(backlog, story_id):
    wanted = story_id.lower()
    for root, _dirs, files in os.walk(backlog):
        for name in files:
            if not name.endswith(".md") or name == "epic.md":
                continue
            path = os.path.join(root, name)
            if os.path.splitext(name)[0].lower() == wanted:
                return path
            try:
                front, _ = read_front_matter(path)
            except GateError:
                continue
            if str(front.get("id", "")).lower() == wanted:
                return path
    raise GateError(
        f"no story {story_id!r} under {backlog}/ — a story is one markdown file "
        f"backlog/<epic>/<story>.md with front matter (see the backlog contract)"
    )


def criteria_of(story_path, body):
    """Acceptance criteria as (key, text) pairs, read from the `## Acceptance criteria`
    section: one `- <key>: <text>` line each. The key is a name, never a number."""
    lines, collecting, found = body.splitlines(), False, []
    for line in lines:
        if line.strip().lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue
        match = CRITERION.match(line.strip())
        if match:
            found.append((match.group(1), match.group(2).strip()))
        elif line.strip().startswith("-"):
            raise GateError(
                f"{story_path}: acceptance criterion {line.strip()!r} has no key — "
                f"write `- <key>: <criterion>` with a lowercase, hyphenated key that "
                f"names the behaviour"
            )
    if not found:
        raise GateError(
            f"{story_path}: no acceptance criteria — add a `## Acceptance criteria` "
            f"section with one `- <key>: <criterion>` line per criterion"
        )
    return found


def epic_of(story_path, front, backlog):
    named = front.get("epic")
    if isinstance(named, list) or not named:
        raise GateError(f"{story_path}: front matter has no `epic:`")
    for candidate in (
        os.path.join(os.path.dirname(story_path), "epic.md"),
        os.path.join(backlog, str(named), "epic.md"),
    ):
        if os.path.isfile(candidate):
            return candidate, str(named)
    raise GateError(
        f"{story_path}: epic {named!r} has no epic.md — create "
        f"{os.path.join(backlog, str(named), 'epic.md')}"
    )


# --- checks -----------------------------------------------------------------

def check_contract(result, profile):
    """The profile may declare which gate contract it was written for.

    Undeclared is the normal case and no finding: a profile with today's keys is what the template
    writes. A *higher* number than this gate knows is a refusal — the project has keys this script
    would ignore, and ignoring a key silently is how a check disappears without anyone noticing.
    """
    declared = str(profile.get("contract", "")).strip()
    if not declared:
        result.note("contract", f"profile declares no `contract:` — read as {CONTRACT} "
                                f"(gate {VERSION})")
        return
    if not declared.isdigit():
        result.fail("contract", f"profile's `contract: {declared}` is not a number")
        return
    if int(declared) > CONTRACT:
        result.fail(
            "contract",
            f"the profile is written for gate contract {declared} and this gate implements "
            f"{CONTRACT} (gate {VERSION}) — re-run `factory.sh install` before trusting a run, "
            f"because this script would ignore whatever the newer contract added",
        )
    elif int(declared) < CONTRACT:
        result.note(
            "contract",
            f"the profile declares contract {declared} and this gate implements {CONTRACT} "
            f"(gate {VERSION}) — still read, and worth bringing up to date",
        )
    else:
        result.ok("contract", f"profile and gate agree on contract {CONTRACT} (gate {VERSION})")


def check_status(result, story_path, front):
    """A story a human has not released is not a story the pipeline builds. A story
    without the field at all is not blocked — the project may not use the field."""
    status = str(front.get("status", "")).strip().lower()
    if not status:
        result.skip("approved", f"{story_path}: no `status:` field — nothing to release")
    elif status == "approved":
        result.ok("approved", "story is approved")
    else:
        result.fail(
            "approved",
            f"{story_path}: status is {status!r} — a human releases the story "
            f"(`status: approved`) before code is written. The most expensive mistake is "
            f"well-built wrong code.",
        )


def check_rounds(result, tasks, story_id):
    """The repeat counter lives in a file, so an in-session run cannot lose count and a
    resumed run sees the same number."""
    path = os.path.join(tasks, story_id, ".rounds")
    if not os.path.isfile(path):
        return
    try:
        rounds = int(read_text(path).strip() or "0")
    except (ValueError, GateError):
        result.fail("rounds", f"{path}: not a number")
        return
    if rounds >= MAX_ROUNDS:
        result.fail(
            "rounds",
            f"{path}: {rounds} rounds without convergence — stop and escalate. A loop that "
            f"finds the same thing three times finds it the fourth time too.",
        )
    else:
        result.ok("rounds", f"round {rounds + 1} of at most {MAX_ROUNDS}")


def find_first(cwd, candidates):
    for candidate in candidates:
        if os.path.isfile(os.path.join(cwd, candidate)):
            return candidate
    return None


def check_context_map(result, cwd, profile, context):
    """A story names the context it changes; that context must be on the map. A project without
    a map is not blocked — it has nothing to contradict yet."""
    named = profile.get("contextMap")
    path = named if named and os.path.isfile(os.path.join(cwd, named)) else find_first(
        cwd, CONTEXT_MAP_CANDIDATES
    )
    if not path:
        result.skip("context-map", "the project keeps no context map")
        return
    text = read_text(os.path.join(cwd, path)).lower()
    if context.lower() in text:
        result.ok("context-map", f"context {context!r} is on {path}")
    else:
        result.fail(
            "context-map",
            f"{path}: context {context!r} does not appear — a story either changes a context that "
            f"exists on the map, or it is a scoping question, not a story",
        )


def check_instruction_size(result, cwd):
    """A note, not a check: instructions past a tool's document budget are truncated silently,
    so a run can be missing half its rules without anything saying so."""
    for name in INSTRUCTION_FILES:
        path = os.path.join(cwd, name)
        if not os.path.isfile(path):
            continue
        size = os.path.getsize(path)
        if size > DOC_BUDGET_BYTES:
            result.skip(
                "instruction-size",
                f"{name} is {size} bytes, past the {DOC_BUDGET_BYTES}-byte budget some tools load "
                f"— the rest is truncated silently; move detail into referenced files",
            )
        else:
            result.ok("instruction-size", f"{name} is {size} bytes, within a tool's budget")
        return


def glossary_files(cwd, profile):
    named = profile.get("glossary")
    if named:
        matches = [
            os.path.join(root, f)
            for root, _dirs, files in os.walk(cwd)
            for f in files
            if os.path.join(root, f).endswith(named)
        ]
        if matches:
            return matches
    found = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in ("build", "out", "bin", "obj", "target", "node_modules", ".git")]
        found += [os.path.join(root, f) for f in files if f.lower() == "glossary.md"]
    return found


def check_proposals_landed(result, tasks, story_id, cwd, profile):
    """Every term the plan proposed is either in a glossary now or named as still open. A
    proposal that quietly disappears is how a model's private vocabulary enters a code base."""
    plan_path = os.path.join(tasks, story_id, "plan.md")
    try:
        plan = read_text(plan_path)
    except GateError:
        return
    proposals, collecting = [], False
    for line in plan.splitlines():
        if line.strip().lower().startswith("## glossary proposals"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting and line.strip().startswith("-") and ":" in line:
            proposals.append(line.strip()[1:].split(":", 1)[0].strip().strip("`*"))
    if not proposals:
        return
    files = glossary_files(cwd, profile)
    if not files:
        result.skip(
            "glossary",
            f"{len(proposals)} term(s) proposed in the plan, but the project keeps no glossary",
        )
        return
    corpus = "\n".join(read_text(f).lower() for f in files)
    document = ""
    try:
        document = read_text(os.path.join(tasks, story_id, "document.md")).lower()
    except GateError:
        pass
    missing = [
        term
        for term in proposals
        if term.lower() not in corpus and term.lower() not in document
    ]
    if missing:
        result.fail(
            "glossary",
            f"proposed but neither in a glossary nor named as open: {', '.join(missing)} — a term "
            f"the code uses and no glossary defines is private vocabulary",
        )
    else:
        result.ok("glossary", f"{len(proposals)} proposed term(s) accounted for")


def check_epic(result, story_path, front, backlog):
    epic_path, epic_name = epic_of(story_path, front, backlog)
    epic_front, _ = read_front_matter(epic_path)
    # A key with no value parses as an empty list, and `str([])` is "[]" — non-empty, so the field
    # would count as filled. A mandatory field is a sentence, so only a non-empty string counts.
    missing = [f for f in EPIC_FIELDS
               if not (isinstance(epic_front.get(f), str) and epic_front[f].strip())]
    if missing:
        result.fail(
            "epic",
            f"{epic_path}: epic {epic_name!r} is incomplete — missing "
            f"{', '.join(missing)}. An epic states why it exists (intent), what "
            f"changes for the user (goal), which outcome event measures it (metric) "
            f"and who answers domain questions (domain_contact).",
        )
    else:
        result.ok("epic", f"epic {epic_name!r} complete ({', '.join(EPIC_FIELDS)})")


def read_mapping(tasks, story_id):
    """criterion key -> list of test selectors, from the gate:tests table."""
    path = os.path.join(tasks, story_id, "tests.md")
    text = read_text(path)
    if "<!-- gate:tests -->" not in text:
        raise GateError(
            f"{path}: no `<!-- gate:tests -->` table — the test stage records one row "
            f"per acceptance criterion: | <criterion key> | <Class>#<method> |"
        )
    mapping = {}
    for line in text.split("<!-- gate:tests -->", 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        row = MAPPING_ROW.match(stripped)
        if not row:
            continue
        key, selector = row.group(1), row.group(2).strip()
        if key in ("criterion", "---"):
            continue
        if not SELECTOR.match(selector):
            raise GateError(
                f"{path}: test selector {selector!r} is not `<Class>#<method>` "
                f"(fully qualified class, then the test method)"
            )
        mapping.setdefault(key, []).append(selector)
    return path, mapping


def check_mapping(result, tasks, story_id, criteria):
    try:
        path, mapping = read_mapping(tasks, story_id)
    except GateError as error:
        result.fail("tests-mapped", str(error))
        return {}
    uncovered = [key for key, _ in criteria if key not in mapping]
    if uncovered:
        result.fail(
            "tests-mapped",
            f"{path}: no end-user test for {', '.join(uncovered)} — every acceptance "
            f"criterion needs at least one test, or the build gate can never fail on it.",
        )
    unknown = [key for key in mapping if key not in {k for k, _ in criteria}]
    if unknown:
        result.fail(
            "tests-mapped",
            f"{path}: test rows name criteria the story does not have: {', '.join(unknown)}",
        )
    if not uncovered and not unknown:
        result.ok(
            "tests-mapped",
            f"{sum(len(v) for v in mapping.values())} test(s) mapped to "
            f"{len(criteria)} criterion(s)",
        )
    return mapping


def check_exists(result, cwd, mapping):
    """A selector must point at a test that is actually there. Without this check a
    missing test looks exactly like a red one, and the run would certify nothing.

    Two shapes resolve a selector's class part to a file, and both are strict about it:

    * **a file named after the class** — `com.example.WidgetTest#shows` lives in `WidgetTest.java`
      wherever that file is. JUnit, xUnit, NUnit, MSTest, Kotlin: one class per file.
    * **a file named by the module path** — `tests.test_widgets#test_shows` lives in
      `tests/test_widgets.py`, and `tests.test_widgets.TestWidgets#test_shows` in the same file.
      The class part is read as a dotted path; the longest prefix that *is* a file (by path, not by
      basename) is the module, and every remaining segment must be declared in it. pytest, and any
      stack whose tests are functions in a module.

    A basename that happens to match elsewhere never counts for the second shape: `com.example`
    would have to exist as `com/example.<ext>`, which is what keeps a Java class in a file not
    named after it *not found*, exactly as before.
    """
    if not mapping:
        return
    sources, by_path = {}, {}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [
            d
            for d in dirs
            if d not in ("build", "out", "bin", "obj", "target", "node_modules", ".git")
        ]
        for name in files:
            full = os.path.join(root, name)
            sources.setdefault(os.path.splitext(name)[0], []).append(full)
            stem = os.path.splitext(os.path.relpath(full, cwd))[0].replace(os.sep, "/")
            by_path.setdefault(stem, []).append(full)
    located = {}
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            cls, method = SELECTOR.match(selector).groups()
            simple = cls.rsplit(".", 1)[-1]
            candidates = sources.get(simple, [])
            found = [path for path in candidates if contains(path, method)]
            shape = "a file named after the class"
            if not found and not candidates:
                found = module_files(by_path, cls, method)
                shape = "the module path"
            if found:
                located[selector] = os.path.relpath(found[0], cwd)
                result.ok(
                    "tests-exist",
                    f"{selector} found in {located[selector]} ({key}, by {shape})",
                )
            elif candidates:
                result.fail(
                    "tests-exist",
                    f"{selector}: {os.path.relpath(candidates[0], cwd)} has no {method} — "
                    f"criterion {key!r} has no test, only a row in the table",
                )
            else:
                result.fail(
                    "tests-exist",
                    f"{selector}: no source file for {simple} — criterion {key!r} has no "
                    f"test, and a missing test is indistinguishable from a red one at "
                    f"the runner",
                )
    return located


def contains(path, needle):
    """Whether a source file mentions the identifier. Unreadable (binary) files do not."""
    try:
        with open(path, encoding="utf-8") as handle:
            return needle in handle.read()
    except (UnicodeDecodeError, OSError):
        return False


def module_files(by_path, cls, method):
    """The files a dotted class part names as a module path, longest prefix first.

    `a.b.C` is tried as the file `a/b/C.*`, then `a/b.*` holding `C`, then `a.*` holding `b` and
    `C` — each as a path suffix of some source file, never as a bare basename. The remaining
    segments and the method must all appear in the file, so a module that has the function but not
    the class it is claimed to sit in is not a match either.
    """
    segments = cls.split(".")
    for cut in range(len(segments), 0, -1):
        prefix, rest = "/".join(segments[:cut]), segments[cut:]
        hits = [path for stem, paths in by_path.items()
                if stem == prefix or stem.endswith("/" + prefix)
                for path in paths]
        found = [path for path in hits
                 if all(contains(path, name) for name in rest) and contains(path, method)]
        if found:
            return found
    return []


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


def run(command, cwd):
    """Run one profile command through a shell.

    The profile is written for a POSIX shell — `a && b`, `sh runner.sh`, quoting — and the runner
    and the commit hook are bash, so on Windows the same commands go through Git's bash (see
    `posix_shell`). Without one, `cmd.exe` gets them, and a profile that leans on POSIX syntax
    fails there loudly rather than subtly.
    """
    bash = posix_shell()
    if bash:
        completed = subprocess.run(
            [bash, "-c", command], cwd=cwd, capture_output=True, text=True
        )
        return completed.returncode, completed.stdout + completed.stderr
    completed = subprocess.run(
        command, cwd=cwd, shell=True, capture_output=True, text=True
    )
    return completed.returncode, (completed.stdout + completed.stderr)


def check_compiles(result, profile, cwd):
    command = profile.get("compile")
    if not command:
        result.skip("compiles", "no `compile:` command in the stack profile")
        return
    code, output = run(command, cwd)
    if code == 0:
        result.ok("compiles", f"`{command}` succeeded")
    else:
        result.fail("compiles", f"`{command}` failed:\n{tail(output)}")


#: A markdown table row, split into its cells. The first cell names the thing, the **last**
#: names how it was checked — the tables differ in width, so counting from the left is wrong.
PATHLIKE = re.compile(r"`([\w./-]+\.[A-Za-z0-9]{1,6})`")
#: A cited path usually carries where in the file it was read: `README.md:149`, `Book.cs:28-31`,
#: `guide.md#anchor`. The location is not part of the file name, so it is stripped before the file
#: is looked up — otherwise naming the line makes an existing file look missing.
LOCATION_SUFFIX = re.compile(r"(?::L?\d+(?:[-–:]\d+)?|#[\w.-]+)$")


def bare_path(name):
    return LOCATION_SUFFIX.sub("", name.strip().strip("`")).strip()


def row_cells(line):
    """Cells of a markdown table row, or an empty list when the line is not one."""
    if not line.startswith("|"):
        return []
    return [cell.strip() for cell in line.strip("|").split("|")]


#: What a table row writes when there is nothing to list: a document stage that changed nothing says
#: so in one row and why, and that row names no file.
NOTHING = {"", "—", "–", "-", "none", "n/a", "nothing"}


def check_documented(result, tasks, story_id, cwd):
    """The document stage may only write statements that can be checked. Two of them can be
    checked here: a file it says it updated exists, and every glossary row names where its
    definition came from. A documented path that does not resolve outlives the story."""
    path = os.path.join(tasks, story_id, "document.md")
    try:
        text = read_text(path)
    except GateError as error:
        result.fail("documented", str(error))
        return
    if needs_human_ids(text) is not None:
        result.fail(
            "documented",
            f"{path}: the stage stopped with a needs-human section — read it and decide",
        )
        return

    section, missing, unsourced, files = None, [], [], 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().lower()
            continue
        cells = row_cells(stripped)
        if len(cells) < 3 or cells[0].lower() in ("term", "file") or set(cells[0]) <= {"-", " "}:
            continue
        name, source = cells[0].strip("`"), cells[-1]
        if section == "documents updated" and name.strip().lower() in NOTHING:
            if not source:
                unsourced.append("the row saying nothing was updated (no `Verified by`)")
            continue
        if section == "documents updated":
            files += 1
            target = bare_path(name)
            if target and not os.path.exists(os.path.join(cwd, target)):
                missing.append(name)
            if not source:
                unsourced.append(f"{name} (no `Verified by`)")
        elif section == "glossary" and not source:
            unsourced.append(f"glossary term {name!r}")

    for name in PATHLIKE.findall(text):
        target = bare_path(name)
        if "/" in target and not os.path.exists(os.path.join(cwd, target)):
            missing.append(name)

    if missing:
        result.fail(
            "documented",
            f"{path}: names things that do not exist: {', '.join(sorted(set(missing)))} — a "
            f"documented path that does not resolve sends the next reader nowhere. Write every "
            f"path as it resolves from the project root, not as a package- or namespace-relative "
            f"shorthand.",
        )
    if unsourced:
        result.fail(
            "documented",
            f"{path}: unsourced claims: {', '.join(unsourced)} — every row says how it was checked",
        )
    if not missing and not unsourced:
        result.ok("documented", f"{files} document(s) updated, every claim resolves")


#: Extra profile commands run per stage, in this order. A key the profile does not
#: declare is skipped and named — a gate that fails on a command nobody configured
#: gets switched off, and then there is no governance at all.
STAGE_CHECKS = {
    "test": (),
    "build": ("architecture", "format"),
    # The tidy stage changes no behaviour, so its whole claim is that everything still holds:
    # the same commands as the build stage, run again after the refactor.
    "tidy": ("architecture", "format"),
    "document": ("architecture",),
}


def check_stage_commands(result, profile, cwd, stage):
    """The gate must not *know* its checks, it looks them up. Adding a capability is
    then one line in the profile, not an edit to a stage."""
    for key in STAGE_CHECKS.get(stage, ()):
        command = profile.get(key)
        if not command:
            result.skip(key, f"no `{key}:` command in the stack profile")
            continue
        code, output = run(command, cwd)
        if code == 0:
            result.ok(key, f"`{command}` succeeded")
        else:
            result.fail(key, f"`{command}` failed:\n{tail(output)}")



#: Which declared command can run a given test. A mapped test may live in any test project or
#: source set — the end-user tests in one, the unit tests in another — and running a selector
#: against the wrong one matches nothing. A runner that matched nothing exits 0, which is
#: indistinguishable from a passing test, so the choice may not be a guess: it is made from the
#: file the test was found in.
TEST_COMMAND_KEYS = ("e2eTest", "test")


def test_command_keys(profile):
    """Every command in the profile that runs tests, most specific first.

    A project has more than two test source sets — unit, integration, end-user — and a mapped
    test may live in any of them. Beyond the two fixed keys, any `test.<name>:` entry counts, so
    declaring one more source set is a profile line and never a change to the gate.
    """
    extra = sorted(key for key in profile if key.startswith("test."))
    return extra + list(TEST_COMMAND_KEYS)


def command_for(profile, test_path):
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


#: Where test runners leave a report of what they actually executed. These are file-format
#: conventions rather than knowledge about any one tool: JUnit XML (Gradle, Maven, most JVM
#: runners) and TRX (the .NET test platform). A project whose reports live elsewhere says so with
#: `testReport: <glob>`.
REPORT_GLOBS = (
    "**/build/test-results/**/*.xml",
    "**/target/surefire-reports/*.xml",
    "**/target/failsafe-reports/*.xml",
    "**/test-results/**/*.xml",
    "**/TestResults/**/*.trx",
    "**/*.trx",
)
#: A selector no project can contain — the control run's subject (see `discriminates`): the class,
#: the method, and the file a `{file}` placeholder would name for it.
SENTINEL = ("dev.dca.factory.NoSuchTestClass", "noSuchTestMethod", "dev/dca/factory/NoSuchTest.py")


def fill(fmt, cls, method, test_path=None):
    """The runner's filter argument for one selector.

    `{class}` and `{method}` are the selector's two halves. `{file}` is the source file the selector
    was located in, relative to the project root and with forward slashes — the handle runners
    that select by path want (`pytest tests/test_x.py::test_y`), which no dotted name gives them.
    """
    text = fmt.replace("{class}", cls).replace("{method}", method)
    if test_path is not None:
        text = text.replace("{file}", test_path.replace(os.sep, "/"))
    return text
NOISE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds|minutes)\b|\b\d{2}:\d{2}:\d{2}\b")


def normalise(output, cwd):
    text = output.replace(cwd, ".")
    return NOISE.sub("<time>", text).strip()


def report_state(cwd, profile):
    """{path: (digest, mtime)} of every candidate report file right now."""
    patterns = [profile["testReport"]] if profile.get("testReport") else list(REPORT_GLOBS)
    state = {}
    for pattern in patterns:
        for path in glob.glob(os.path.join(cwd, pattern), recursive=True):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as handle:
                    state[path] = (hashlib.sha256(handle.read()).hexdigest(),
                                   os.path.getmtime(path))
            except OSError:
                continue
    return state


def clock_marker(cwd):
    """A file written now, to read the *filesystem's* clock rather than this process's.

    Comparing report timestamps against `time.time()` imports clock skew and the filesystem's
    granularity into the check; comparing them against a file written at the same moment does not.
    """
    path = os.path.join(cwd, ".factory-gate-marker")
    try:
        with open(path, "w") as handle:
            handle.write("")
        stamp = os.path.getmtime(path)
        os.remove(path)
        return stamp
    except OSError:
        return None


def reports_from_this_run(before, after, marker):
    """The report files this invocation created or rewrote.

    Two signals, because neither alone is enough. Content: a report whose bytes changed is new
    evidence — but a deterministic runner can write the same bytes twice. Time against the marker:
    a report touched after the invocation began is this run's — while a report left by an earlier
    run keeps its older timestamp and stays out, which is the case this check exists for.
    """
    fresh = []
    for path, (digest, mtime) in after.items():
        was = before.get(path)
        if was is None or was[0] != digest:
            fresh.append(path)
        elif marker is not None and mtime >= marker:
            fresh.append(path)
    return fresh


#: One test, several report cases: a parametrised test reports `test_x[a]`, `test_x[b]`, …, and a
#: JUnit writer may append the signature, `test_x(int)`. All of them are the mapped test, and one
#: failing case fails it — so the outcomes merge, and failed wins.
OUTCOME_RANK = {"failed": 2, "passed": 1, "skipped": 0}


def executed_tests(paths):
    """{(class, method): outcome} for every test a report says ran. Outcome is 'passed' or 'failed'.

    Two formats, because two are enough to cover the runners this is used with. A report is the
    only artefact that states what was *executed*: an exit code says how a process ended, and a
    message says what a process printed — neither says a test ran.
    """
    ran = {}

    def record(cls, method, outcome):
        key = (cls, re.split(r"[(\[]", method, maxsplit=1)[0])
        if OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(ran.get(key), -1):
            ran[key] = outcome
    for path in paths:
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError):
            continue
        for case in root.iter():
            tag = case.tag.rsplit("}", 1)[-1]
            if tag == "testcase":                                   # JUnit XML
                cls = (case.get("classname") or "").strip()
                method = (case.get("name") or "").strip()
                outcome = "passed"
                for child in case:
                    if child.tag.rsplit("}", 1)[-1] in ("failure", "error"):
                        outcome = "failed"
                    elif child.tag.rsplit("}", 1)[-1] == "skipped":
                        outcome = "skipped"
                if method:
                    record(cls, method, outcome)
            elif tag == "UnitTestResult":                           # TRX
                name = (case.get("testName") or "").strip()
                outcome = (case.get("outcome") or "").strip().lower()
                if name:
                    cls, _, method = name.rpartition(".")
                    record(cls, method,
                           "passed" if outcome == "passed" else
                           "skipped" if outcome in ("notexecuted", "skipped") else "failed")
    return ran


#: How a test's *reported* name is declared in code where it differs from the method name. Two
#: forms cover the runners whose reports drop the method name; every other stack reports the method
#: and never reaches this.
DISPLAY_NAME = (
    re.compile(r'@DisplayName\s*\(\s*"((?:[^"\\]|\\.)*)"'),           # JUnit 5
    re.compile(r'DisplayName\s*=\s*"((?:[^"\\]|\\.)*)"'),              # xUnit [Fact(DisplayName=…)]
    re.compile(r'Description\s*=\s*"((?:[^"\\]|\\.)*)"'),              # NUnit [Test(Description=…)]
)


def display_name_of(test_path, method):
    """The name this method is reported under, read from the code that declares it.

    A report that carries a display name instead of a method name needs a mapping, and the only
    honest place to get one is the declaration: the annotation sits on the method. Guessing from
    class membership instead would let a sibling's result stand in for this test.
    """
    text = read_text(test_path) if test_path and os.path.isfile(test_path) else ""
    if not text:
        return None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(rf"\b{re.escape(method)}\s*\(", line):
            for candidate in reversed(lines[max(0, index - 6):index + 1]):
                for pattern in DISPLAY_NAME:
                    match = pattern.search(candidate)
                    if match:
                        return match.group(1)
                if candidate.strip().endswith("}") and candidate is not lines[index]:
                    break                     # left this method's declaration
    return None


def outcome_for(ran, cls, method, display=None):
    """What a report says about this selector: (outcome, how it was matched) or (None, "").

    The method name is the better key, but it is not always in the report — a JUnit XML writer puts
    the *display* name in `name`, so a test with a readable title loses its method name there. The
    class always survives, and the run was filtered to one selector, so a case reported for that
    class is this test. Where several appear, the filter was not honoured and the verdict covers
    them all, which the report says out loud rather than pretending precision.
    """
    simple = cls.rsplit(".", 1)[-1]

    def same_class(report_class):
        return (not report_class or report_class == cls
                or report_class.rsplit(".", 1)[-1] == simple
                or report_class.endswith("." + simple)
                or simple in report_class.split("."))

    for (report_class, report_method), outcome in ran.items():
        if report_method == method and same_class(report_class):
            return outcome, "by name"
    if display:
        for (report_class, report_method), outcome in ran.items():
            if report_method == display and same_class(report_class):
                return outcome, f"by the display name declared in the code ({display!r})"
    # Nothing below the name. Membership of the same class is not a mapping: a runner that ignores
    # the filter, or a filter that matches a sibling, produces exactly one case for the class that
    # is *not* this test — and counting it would let one test's outcome decide another's criterion.
    # A report without this test's name, or without the display name its declaration sets, is no
    # evidence, and the names it did carry are worth printing.
    in_class = sorted(m for (report_class, m), _o in ran.items() if same_class(report_class))
    if not in_class:
        return None, ""
    return None, (f"the report holds {len(in_class)} case(s) for that class "
                  f"({', '.join(in_class[:4])}) and none is named {method!r}"
                  + (f" or {display!r}" if display else "")
                  + (", and no display name is declared on it" if not display else ""))


def discriminates(command, flag, fmt, cwd, cache):
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

def check_test_state(result, profile, cwd, mapping, expected, located=None, tasks=None, story=None):
    """expected 'red': every mapped test must fail. 'green': all must pass."""
    fallback = profile.get("e2eTest") or profile.get("test")
    flag = profile.get("filterFlag", "")
    fmt = profile.get("filterFormat", "{class}.{method}")
    located = located or {}
    if not fallback:
        result.skip(
            f"tests-{expected}",
            "no `e2eTest:` or `test:` command in the stack profile",
        )
        return
    if not mapping:
        return
    ledger = red_ledger_path(tasks, story)
    have_ledger = bool(ledger) and os.path.isfile(ledger)
    was_red = read_red_ledger(tasks, story)
    now_red = set()
    control = {}                              # one control run per command, not per selector
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            cls, method = SELECTOR.match(selector).groups()
            test_path = located.get(selector)
            if "{file}" in fmt and not test_path:
                # The filter names the file, and no file was found for this selector — running the
                # placeholder literally would select nothing, and that exits 0 on some runners.
                result.fail(
                    f"tests-{expected}",
                    f"{selector}: `filterFormat` selects by `{{file}}`, but no source file was "
                    f"located for it — nothing to run for {key!r}.",
                )
                continue
            pattern = fill(fmt, cls, method, test_path)
            command_key, command = command_for(profile, test_path) if test_path else (None, None)
            if not command and test_path:
                # Running it with some other command proves nothing in either direction: a runner
                # that matched no test exits 0 on one stack (looks green) and non-zero on another
                # (looks red). Both are artefacts, so this is a configuration error, not a verdict.
                result.fail(
                    f"tests-{expected}",
                    f"{selector} lives in {test_path}, which no declared test command covers. "
                    f"Declare that source set in the stack profile (`test.<name>: <command>`), or "
                    f"state the scope of a command that already runs it (`covers.<key>: <paths>` "
                    f"or `covers.<key>: **`); "
                    f"a run with any other command would match no test, and that exits 0 on one "
                    f"runner and non-zero on another — neither is evidence about {key!r}.",
                )
                continue
            if not command:
                command_key, command = "e2eTest" if profile.get("e2eTest") else "test", fallback
            invocation = f'{command} {flag} "{pattern}"'.strip()
            evidence = ""
            reporting = profile.get("testEvidence", "").strip() != "exit-code"
            before_reports = report_state(cwd, profile) if reporting else {}
            marker = clock_marker(cwd) if reporting else None
            code, output = run(invocation, cwd)

            # What the test *did* comes from the runner's report, because that is the only artefact
            # that states which tests were executed. An exit code says how a process ended; a
            # message says what it printed. Neither says a test ran — a runner that answers "no
            # tests found for <selector>" produces a different exit code and a different line for
            # every selector while executing nothing at all.
            if profile.get("testEvidence", "").strip() == "exit-code":
                control_code, control_output = discriminates(command, flag, fmt, cwd, control)
                if code == control_code and normalise(output, cwd) == control_output:
                    result.fail(
                        f"tests-{expected}",
                        f"{selector}: `{invocation}` answers a selector that cannot exist the same "
                        f"way (exit {code}), so it never ran this test — no evidence about {key!r}:"
                        f"\n{tail(output)}",
                    )
                    continue
                result.skip(
                    f"tests-{expected}",
                    f"{selector}: `testEvidence: exit-code` — the verdict rests on the exit code, "
                    f"not on a report of what ran. A runner that exits like a failing test without "
                    f"running one is indistinguishable here.",
                )
            else:
                reports = reports_from_this_run(before_reports, report_state(cwd, profile), marker)
                display = display_name_of(located.get(selector), method)
                outcome, how = outcome_for(executed_tests(reports), cls, method, display)
                if outcome is None:
                    detail = (f" — {how}" if how else
                              f" ({len(reports)} report file(s) written by this run)")
                    result.fail(
                        f"tests-{expected}",
                        f"{selector}: no test report from this run shows it ran{detail}. Let the "
                        f"runner write one (JUnit XML is the default on the JVM; .NET needs "
                        f"`--logger trx`), point `testReport:` at it, give the test a name the "
                        f"report carries, or accept the weaker check with "
                        f"`testEvidence: exit-code`:\n{tail(output)}",
                    )
                    continue
                if outcome == "skipped":
                    result.fail(
                        f"tests-{expected}",
                        f"{selector} was skipped rather than run, so it says nothing about "
                        f"{key!r}.",
                    )
                    continue
                # The report decides, not the exit code: a build can fail for reasons beside this
                # test, and a runner can exit 0 with a failure recorded.
                code = 0 if outcome == "passed" else 1
                evidence = f"report {how}"

            passed = code == 0
            if not passed:
                now_red.add(selector)
            if expected == "green" and passed and not have_ledger:
                # No test stage ran in this checkout — the run artefacts may simply not be
                # committed. Say that the evidence is missing instead of inventing either verdict.
                result.skip(
                    "tests-green",
                    f"{selector} is green, but no `{os.path.basename(ledger)}` from a test stage "
                    f"is present here, so nothing proves it ever failed ({key!r}).",
                )
                continue
            if expected == "green" and passed and selector not in was_red:
                # Never seen red: a runner that matched nothing exits 0 exactly like a passing
                # test, so "green" alone is no evidence that this test ran at all.
                result.fail(
                    "tests-green",
                    f"{selector} passes now but was never recorded red by the test stage "
                    f"({key!r}) — a test that never failed proves nothing, and a run that "
                    f"matched no test passes too. Run `--stage test` before the build stage.",
                )
                continue
            if expected == "red" and passed:
                result.fail(
                    "tests-red",
                    f"{selector} passes before the build stage — a test that is green "
                    f"before the code exists proves nothing about {key!r}. Either the test "
                    f"asserts nothing new (the test stage fixes it), or {key!r} describes "
                    f"behaviour the system already has — then the criterion does not belong in "
                    f"the story, and that is the story author's call, not a stage's.",
                )
            elif expected == "green" and not passed:
                result.fail(
                    "tests-green",
                    f"{selector} fails, so criterion {key!r} is not met:\n{tail(output)}",
                )
            else:
                result.ok(
                    f"tests-{expected}",
                    f"{selector} is {'green' if passed else 'red'} ({key}, via `{command_key}:`"
                    f"{', ' + evidence if evidence else ''})",
                )
    if expected == "red":
        write_red_ledger(tasks, story, now_red)


#: Which selectors the test stage saw fail. Kept as a file next to the round counter for the same
#: reason: the build gate must not take a stage's word that a test was red once.
def red_ledger_path(tasks, story):
    if not tasks or not story:
        return None
    return os.path.join(tasks, story, ".tests-red")


def read_red_ledger(tasks, story):
    path = red_ledger_path(tasks, story)
    if not path or not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def write_red_ledger(tasks, story, selectors):
    path = red_ledger_path(tasks, story)
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(sorted(selectors)) + ("\n" if selectors else ""))


def tail(output, limit=1200):
    text = output.strip()
    return text[-limit:] if len(text) > limit else text


# --- result -----------------------------------------------------------------

# --- decisions: the question a stage may not answer, kept where the answer can land ------------
#
# A stage that cannot decide writes `## needs-human` and the run stops. The question itself lives
# in a record of its own, `<store>/<story>-<nn>.md` — markdown with front matter, committed with
# the project — because the stage file has no place for an answer and no second session would find
# one there. State is read from the record, never stored in it: no `## Answer` is open; an
# `## Answer` with `answer:`, `by:` and `at:` is answered; a gate-written `## Applied` is applied.
# A draft that lacks the actor or the time is not an answer — an unconfirmed draft unblocks nothing.
DECISIONS_DIR = os.path.join(".agents", "factory", "decisions")
STAGE_FILES = {"plan": "plan.md", "test": "tests.md", "build": "build.md", "tidy": "tidy.md",
               "judge": "judge.md", "document": "document.md"}
ANSWER_FIELDS = ("answer", "by", "at")


def section_of(text, heading):
    """The lines under `## <heading>` up to the next `## `, or None when the section is absent."""
    lines, inside, body = text.splitlines(), False, []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if inside:
                break
            inside = stripped[3:].split("(")[0].strip().lower() == heading
            continue
        if inside:
            body.append(line)
    return body if inside or body else None


def fields_of(lines):
    """`key: value` pairs in a section, first occurrence wins."""
    data = {}
    for line in lines or []:
        stripped = line.strip().lstrip("-").strip()
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            data.setdefault(key.strip().lower(), value.strip())
    return data


def decision_state(text):
    """('open' | 'draft' | 'answered' | 'applied', answer fields)."""
    answer = fields_of(section_of(text, "answer"))
    if section_of(text, "applied") is not None:
        return "applied", answer
    if section_of(text, "answer") is None:
        return "open", answer
    if all(answer.get(field) for field in ANSWER_FIELDS):
        return "answered", answer
    return "draft", answer


def read_decisions(store, story_id):
    """[(path, front, body, state, answer)] for every record that names this story, in id order.

    A record the gate cannot read is a refusal, not a skip: a broken record hides a question."""
    if not os.path.isdir(store):
        return []
    records = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(store, name)
        front, body = read_front_matter(path)
        if str(front.get("story", "")).strip() != story_id:
            continue
        if str(front.get("id", "")).strip() != name[:-3]:
            raise GateError(
                f"{path}: `id:` is {front.get('id')!r}, the file is named {name[:-3]!r} — a "
                f"record is found by its file name, so the two must agree")
        state, answer = decision_state(body)
        records.append((path, front, body, state, answer))
    return records


def needs_human_ids(text):
    """The decision ids a `## needs-human` section names (`decision: <id>`), or [] without one;
    None when the file has no such section at all — or only the heading, left empty or filled with
    `(none)` from the file template: that asks nobody anything, and reading it as a stop halts a
    finished stage."""
    section = section_of(text, "needs-human")
    if section is None or all(line.strip().strip("()").strip().lower() in NOTHING for line in section):
        return None
    return [value for key, value in fields_of(section).items() if key == "decision" and value]


def stamp_applied(path, stage):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"\n## Applied\nat: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                     f"stage: {stage}\n")


def list_decisions(cwd, story_id=None):
    """The inbox: one line per record, open ones first, then drafts, answered, applied.

    `<id>  <state>  <story>/<stage>  asked <time>  <question>` — what a second session needs to
    pick one up without any transcript. Read from the files alone; nothing is inferred."""
    store = os.path.join(cwd, DECISIONS_DIR)
    rows = []
    if os.path.isdir(store):
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(store, name)
            try:
                front, body = read_front_matter(path)
            except GateError as error:
                rows.append((-1, name[:-3], "unreadable", "?", "?", "?", str(error)))
                continue
            story = str(front.get("story", "")).strip()
            if story_id and story != story_id:
                continue
            state, answer = decision_state(body)
            question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
            rank = {"open": 0, "draft": 1, "answered": 2, "applied": 3}[state]
            rows.append((rank, str(front.get("id", name[:-3])).strip(), state, story,
                         str(front.get("stage", "?")).strip(), str(front.get("asked", "?")).strip(),
                         question + (f"  → {answer.get('answer')} by {answer.get('by')}"
                                     if state in ("answered", "applied") else "")))
    rows.sort()
    for _rank, rid, state, story, stage, asked, text in rows:
        print(f"{rid}  {state:<9} {story}/{stage}  asked {asked}  {text}")
    open_count = sum(1 for r in rows if r[2] in ("open", "draft"))
    print(f"decisions: {len(rows)} record(s), {open_count} waiting for an answer"
          + (f" (story {story_id})" if story_id else "")
          + f" — store {DECISIONS_DIR}/")
    return 0


def check_decisions(result, tasks, story_id, cwd, gating=None):
    """Every question this story raised is recorded, and every answer it got has been applied.

    Runs on every stage: an open question blocks the story wherever it stands, and a stage file
    that escalates without a record has asked nobody. `gating` is the stage this gate call is for:
    the plan gate runs *before* its stage, so there an answered plan question is the stage's input,
    not yet something it failed to apply."""
    store = os.path.join(cwd, DECISIONS_DIR)
    try:
        records = read_decisions(store, story_id)
    except GateError as error:
        result.fail("decisions", str(error))
        return
    known = {str(front["id"]).strip(): (path, body, state) for path, front, body, state, _ in records}

    # 1. a stage that stopped must have written a record for its question
    stage_texts = {}
    for stage, name in STAGE_FILES.items():
        path = os.path.join(tasks, story_id, name)
        if not os.path.isfile(path):
            continue
        stage_texts[stage] = read_text(path)
        ids = needs_human_ids(stage_texts[stage])
        if ids is None:
            continue
        if not ids:
            result.fail(
                "decisions",
                f"{path}: `## needs-human` names no `decision: <id>` — the question has to be a "
                f"record under {DECISIONS_DIR}/ so an answer has a place to land; without one, "
                f"nobody was asked.",
            )
        for wanted in ids:
            if wanted not in known:
                result.fail(
                    "decisions",
                    f"{path}: `## needs-human` names decision {wanted!r}, but "
                    f"{DECISIONS_DIR}/{wanted}.md does not exist or names another story.",
                )

    # 2. every record: open blocks, a draft is still open, answered must be applied by its stage
    for path, front, body, state, answer in records:
        rid = str(front["id"]).strip()
        stage = str(front.get("stage", "")).strip()
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        rel = os.path.relpath(path, cwd).replace(os.sep, "/")     # one spelling on every platform
        if state == "open":
            result.fail(
                "decisions",
                f"{rid} is open — {question!r} (asked by stage {stage or '?'}). Answer it in {rel} "
                f"under `## Answer` with `answer:`, `by:` and `at:`; the story waits until then.",
            )
        elif state == "draft":
            missing = ", ".join(f"`{f}:`" for f in ANSWER_FIELDS if not answer.get(f))
            result.fail(
                "decisions",
                f"{rid} has an `## Answer` that is not confirmed — {missing} missing in {rel}. "
                f"A draft unblocks nothing; the person deciding signs it with a name and a time.",
            )
        elif state == "answered":
            text = stage_texts.get(stage)
            still_asking = text is not None and rid in (needs_human_ids(text) or [])
            if gating == "plan" and stage == "plan" and (text is None or still_asking):
                result.note(
                    "decisions",
                    f"{rid} is answered ({answer.get('answer')!r} by {answer.get('by')}) — the plan "
                    f"stage runs next and applies it; the gate after it checks that it did.",
                )
            elif text is None or still_asking:
                result.fail(
                    "decisions",
                    f"{rid} is answered ({answer.get('answer')!r} by {answer.get('by')}), but stage "
                    f"{stage or '?'} has not run with it yet — re-run that stage "
                    f"(`--from {stage}`); it applies the answer and cites `decision: {rid}`.",
                )
            elif rid not in text:
                result.fail(
                    "decisions",
                    f"{rid} is answered and stage {stage} ran again, but "
                    f"{os.path.join(tasks, story_id, STAGE_FILES.get(stage, '?'))} does not cite "
                    f"{rid} — say where the answer landed, so the record can be stamped applied.",
                )
            else:
                stamp_applied(path, stage)
                result.ok("decisions", f"{rid} applied by stage {stage} ({answer.get('answer')!r} "
                                       f"by {answer.get('by')}) — stamped in {rel}")
        else:
            result.ok("decisions", f"{rid} applied ({answer.get('answer')!r} by {answer.get('by')})")
    if not records and not any(state == "fail" and check == "decisions"
                               for state, check, _ in result.entries):
        result.note("decisions", "no decision record for this story")


# --- change check -------------------------------------------------------------

# The same checks outside a story: a direct edit, a commit and CI get one verdict for one tree. The
# profile declares the commands; its `required:` line declares which of them must hold. Without
# that line the check reports what it ran and what it skipped, and fails only on a red command.
CHANGE_CHECKS = ("compile", "test", "architecture", "format")


def git(cwd, *args, env=None):
    try:
        completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    except OSError as error:
        return 1, str(error)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def split_list(value):
    return [part for part in re.split(r"[\s,]+", str(value or "").strip()) if part]


def staged_snapshot(result, cwd, env):
    """The index tree, or None when the working tree differs from it.

    Refuse on drift rather than materialise the index: a check that runs the tests against an
    unstaged fix certifies a commit that does not contain it."""
    code, top = git(cwd, "rev-parse", "--show-toplevel", env=env)
    if code:
        result.fail("snapshot", "--staged needs a git repository")
        return None
    code, tree = git(cwd, "write-tree", env=env)
    if code:
        result.fail("snapshot", f"the index cannot be written as a tree: {tail(tree, 300)}")
        return None
    _, unstaged = git(cwd, "diff", "--name-only", env=env)
    _, untracked = git(cwd, "ls-files", "--others", "--exclude-standard", env=env)
    drift = [f"modified, not staged: {p}" for p in unstaged.splitlines() if p] \
        + [f"untracked: {p}" for p in untracked.splitlines() if p]
    if drift:
        shown = "\n".join("  " + line for line in drift[:10])
        more = f"\n  … and {len(drift) - 10} more" if len(drift) > 10 else ""
        result.fail(
            "snapshot",
            f"the working tree is not what the commit contains — the checks would run against "
            f"these, and the commit would not:\n{shown}{more}\nStage them, or set them aside "
            f"(`git stash push --keep-index --include-untracked`), then commit again.",
        )
        return None
    result.ok("snapshot", f"index tree {tree[:12]} — the working tree matches it")
    return tree


def red(result, check, message, must, strict):
    """A red check fails the verdict — unless a policy is declared and this check is not in it.
    Then the policy decides: the red run is reported, and it is not what the commit is judged by."""
    if strict and not must:
        result.note(check, message + " — optional (not in `required:`), so it does not decide")
    else:
        result.fail(check, message)


def run_test_command(result, cwd, profile, key, command, required, strict=False):
    """A test command passes only when its reports show it executed tests and none failed."""
    before, marker = report_state(cwd, profile), clock_marker(cwd)
    code, output = run(command, cwd)
    ran = executed_tests(reports_from_this_run(before, report_state(cwd, profile), marker))
    executed = sum(1 for outcome in ran.values() if outcome != "skipped")
    failed = sum(1 for outcome in ran.values() if outcome == "failed")
    if code != 0 or failed:
        red(result, "test", f"`{command}` ({key}) failed — {failed} failing case(s):\n{tail(output)}",
            required, strict)
    elif executed:
        result.ok("test", f"`{command}` ({key}) ran {executed} case(s), none failed")
    elif profile.get("testEvidence") == "exit-code":
        result.skip("test", f"`{command}` ({key}) exited 0 and writes no report "
                            f"(`testEvidence: exit-code`) — nothing shows a test ran")
    else:
        message = (f"`{command}` ({key}) exited 0, but no report written by this run shows an "
                   f"executed test — a runner that matched nothing exits 0 too")
        (result.fail if required else result.note if strict else result.skip)("test", message)


def check_required_suites(result, profile, cwd):
    """At build and tidy: the test commands the policy requires, run whole.

    The mapped tests say this story's behaviour holds; they say nothing about the behaviour the
    stories before it delivered. Without a policy the stage gates stay as they were."""
    required = set(split_list(profile.get("required")))
    keys = [k for k in test_command_keys(profile) if k in required and profile.get(k)]
    if not required:
        return
    if not keys:
        result.skip("suite", "`required:` names no declared test command")
    seen = set()
    for key in keys:
        if profile[key] in seen:
            continue
        seen.add(profile[key])
        before = len(result.entries)
        run_test_command(result, cwd, profile, key, profile[key], True, True)
        result.entries[before:] = [(state, "suite", message) for state, _check, message in result.entries[before:]]


def change_check(result, cwd, profile, staged, only):
    # `required:` names profile keys: compile, architecture, format, and each test command by its own
    # key (`test`, `e2eTest`, `test.<name>`) — an end-user suite that needs a running system can be
    # declared without making every commit wait for one.
    required = set(split_list(profile.get("required")))
    unknown = sorted(r for r in required
                     if r not in CHANGE_CHECKS and r != "e2eTest" and not r.startswith("test."))
    if unknown:
        result.fail("policy", f"`required:` names {', '.join(unknown)} — it takes compile, architecture, "
                              f"format and test-command keys (test, e2eTest, test.<name>)")
    if required:
        result.ok("policy", "required: " + " ".join(sorted(required)))
    else:
        result.note("policy", "the profile declares no `required:` — report-only: what is declared "
                              "runs, what is not is named, nothing is mandatory")
    env = dict(os.environ)
    tree = None
    if staged:
        tree = staged_snapshot(result, cwd, env)
        if tree is None:
            return
        # The profile's commands must not inherit a temporary index (`git commit -a`): a test that
        # runs git in a repository of its own would read this commit's index as its own.
        os.environ.pop("GIT_INDEX_FILE", None)
    else:
        code, head = git(cwd, "rev-parse", "--short", "HEAD", env=env)
        result.note("snapshot", "the working tree as it is" + (f", on top of {head}" if code == 0 else ""))
    scope = split_list(only) or list(CHANGE_CHECKS)
    test_keys = [k for k in test_command_keys(profile)] + sorted(
        r for r in required if (r == "e2eTest" or r.startswith("test.")) and r not in test_command_keys(profile))
    for check in CHANGE_CHECKS:
        if check == "test":
            required_tests = [k for k in test_keys if k in required]
            if check not in scope:
                result.skip(check, "not run in this scope" + (
                    f" — {', '.join(required_tests)} required, so a later scope (CI) has to run it"
                    if required_tests else ""))
                continue
            commands = {}
            for key in test_keys:
                if profile.get(key):
                    commands.setdefault(profile[key], []).append(key)
                elif key in required:
                    result.fail("test", f"no `{key}:` command in the stack profile — and `{key}` is required")
            if not commands and not required_tests:
                result.skip("test", "no test command in the stack profile")
            for command, keys in commands.items():
                run_test_command(result, cwd, profile, "/".join(keys), command,
                                 any(k in required for k in keys), bool(required))
            continue
        must = check in required
        if check not in scope:
            result.skip(check, "not run in this scope" + (" — it is required, so a later "
                               "scope (CI) has to run it" if must else ""))
            continue
        key = check
        command = profile.get(key)
        if not command:
            (result.fail if must else result.skip)(
                check, f"no `{key}:` command in the stack profile" + (f" — and `{check}` is required" if must else ""))
            continue
        code, output = run(command, cwd)
        if code == 0:
            result.ok(check, f"`{command}` succeeded")
        else:
            red(result, check, f"`{command}` failed:\n{tail(output)}", must, bool(required))
    if staged:
        _, after = git(cwd, "write-tree", env=env)
        if after != tree:
            result.fail("snapshot", f"the index changed while the checks ran ({tree[:12]} → "
                                    f"{after[:12]}) — what was checked is not what would be committed")


# --- parity -------------------------------------------------------------------

# Several implementations of one behaviour, each proving the same scenarios. The scenario contract is
# markdown: `## <id>`, then `Title:` and `Runs:` lines. A report names a scenario by carrying its
# title as the test's name. Each implementation is checked against the contract — never against the
# other one, because two implementations agreeing on a wrong result is not parity.
SCENARIO_HEADING = re.compile(r"^##\s+(\S+)\s*$")


def read_scenarios(path):
    scenarios, current = [], None
    for line in read_text(path).splitlines():
        match = SCENARIO_HEADING.match(line)
        if match:
            current = {"id": match.group(1), "title": "", "runs": "always"}
            scenarios.append(current)
        elif current is not None and ":" in line and line.split(":", 1)[0].strip().lower() in ("title", "runs"):
            key, value = line.split(":", 1)
            current[key.strip().lower()] = value.strip()
    return [s for s in scenarios if s["title"]]


def reported_names(paths):
    """{test name: outcome} as the report states the name — whole, because a title may hold dots."""
    names = {}
    for path in paths:
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError):
            continue
        for case in root.iter():
            tag = case.tag.rsplit("}", 1)[-1]
            if tag == "testcase":
                name, outcome = (case.get("name") or "").strip(), "passed"
                for child in case:
                    child_tag = child.tag.rsplit("}", 1)[-1]
                    if child_tag in ("failure", "error"):
                        outcome = "failed"
                    elif child_tag == "skipped" and outcome != "failed":
                        outcome = "skipped"
            elif tag == "UnitTestResult":
                name = (case.get("testName") or "").strip()
                raw = (case.get("outcome") or "").strip().lower()
                outcome = "passed" if raw == "passed" else \
                    "skipped" if raw in ("notexecuted", "skipped", "inconclusive") else "failed"
            else:
                continue
            if name and OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(names.get(name), -1):
                names[name] = outcome
    return names


def parity(result, config_path):
    config = read_profile(config_path)
    if not config:
        raise GateError(f"{config_path}: no parity config (`scenarios:` and `implementation.<name>:` lines)")
    base = os.path.dirname(os.path.abspath(config_path))
    contract = os.path.join(base, config.get("scenarios", ""))
    if not config.get("scenarios") or not os.path.isfile(contract):
        raise GateError(f"{config_path}: `scenarios:` names no readable contract ({contract})")
    scenarios = read_scenarios(contract)
    with open(contract, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()[:12]
    result.ok("contract", f"{len(scenarios)} scenario(s) in {config['scenarios']} (sha256 {digest})")
    implementations = sorted(k for k in config if k.startswith("implementation."))
    if not implementations:
        result.fail("implementations", f"{config_path} declares no `implementation.<name>: <report glob>`")
    for key in implementations:
        name = key.split(".", 1)[1]
        paths = sorted(p for p in glob.glob(os.path.join(base, config[key]), recursive=True) if os.path.isfile(p))
        if not paths:
            result.fail(name, f"no report matches {config[key]} — run its suite first")
            continue
        names = reported_names(paths)
        newest = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(os.path.getmtime(p) for p in paths)))
        bound = [s for s in scenarios if s["title"] in names]
        if not bound:
            result.fail(name, f"{len(paths)} report(s) name no scenario of the contract — the binding "
                              f"(the title as the test's name) is gone")
            continue
        problems, unproven = [], []
        for scenario in scenarios:
            outcome = names.get(scenario["title"])
            mandatory = scenario["runs"].strip().lower() == "always"
            if outcome == "passed":
                continue
            if not mandatory and outcome in (None, "skipped"):
                unproven.append(scenario["id"])
                continue
            problems.append(f"{scenario['id']} {outcome or 'missing'} — {scenario['title']!r}")
        if problems:
            result.fail(name, f"{len(problems)} scenario(s) not proven by {len(paths)} report(s):\n"
                        + "\n".join("  " + p for p in problems))
        else:
            result.ok(name, f"{len(scenarios) - len(unproven)} scenario(s) passed in {len(paths)} "
                            f"report(s), newest {newest}")
        if unproven:
            result.note(name, f"not proven here (bound to another configuration): {', '.join(unproven)}")


# --- schedule -----------------------------------------------------------------

# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
STAGE_ORDER = ("plan", "test", "build", "tidy", "judge", "document")
RUNNABLE = ("ready", "in-progress", "resumable")


def depends_on(front):
    """`depends_on: []`, `depends_on: [A, B]` or a `- A` list, as a list of ids."""
    value = front.get("depends_on") or []
    if isinstance(value, str):
        value = [part for part in value.strip().strip("[]").split(",")]
    return [str(part).strip().strip("'\"") for part in value if str(part).strip().strip("'\"")]


def verdict_in(text):
    for line in text.splitlines():
        if line.strip().lower().startswith("verdict:"):
            return line.split(":", 1)[1].strip().strip("`\"' ").lower()
    return ""


def story_state(cwd, tasks, story_id, front):
    """(state, stage to run from or None, detail) for one story, from its files alone."""
    status = str(front.get("status", "")).strip().lower()
    if status == "superseded":
        return "superseded", None, "replaced by another story"
    if status and status != "approved":
        return "unreleased", None, f"status {status} — a human releases it first"
    folder = os.path.join(tasks, story_id)
    texts = {stage: read_text(os.path.join(folder, name)) for stage, name in STAGE_FILES.items()
             if os.path.isfile(os.path.join(folder, name))}
    try:
        records = read_decisions(os.path.join(cwd, DECISIONS_DIR), story_id)
    except GateError as error:
        return "stopped", None, str(error)
    waiting = [str(front_["id"]).strip() for _p, front_, _b, state, _a in records
               if state in ("open", "draft")]
    if waiting:
        return "waiting", None, "decision " + ", ".join(waiting)
    answered = {}
    for _path, front_, _body, state, _answer in records:
        rid, asked_by = str(front_["id"]).strip(), str(front_.get("stage", "")).strip()
        text = texts.get(asked_by)
        if state == "answered" and (text is None or rid in (needs_human_ids(text) or [])):
            answered.setdefault(asked_by, rid)
    if answered:
        stage = min(answered, key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 0)
        return "resumable", stage, f"decision {answered[stage]} answered — its stage applies it"
    rounds_file = os.path.join(folder, ".rounds")
    if os.path.isfile(rounds_file) and (read_text(rounds_file).strip() or "0").isdigit() \
            and int(read_text(rounds_file).strip() or "0") >= MAX_ROUNDS:
        return "stopped", None, f"{MAX_ROUNDS} rounds did not converge"
    if os.path.isfile(os.path.join(folder, ".gate-plan.txt")):
        return "stopped", None, "the plan gate refused the story — the backlog needs a fix"
    for stage, text in texts.items():
        if needs_human_ids(text) is not None:
            return "stopped", None, f"{STAGE_FILES[stage]} ends in `## needs-human` without an open record"
    if verdict_in(texts.get("judge", "")) == "story-conflict":
        return "stopped", None, "the judge found a story conflict"
    refused = [stage for stage in STAGE_ORDER
               if os.path.isfile(os.path.join(folder, f".gate-{stage}.txt"))]
    if refused:
        return "in-progress", refused[0], f"the {refused[0]} gate refused — the stage runs again"
    if "document" in texts:
        return "delivered", None, ""
    if not texts:
        return "ready", "plan", ""
    if verdict_in(texts.get("judge", "")) == "changes-requested":
        return "in-progress", "build", "the judge requested changes"
    missing = next(stage for stage in STAGE_ORDER if stage not in texts)
    return "in-progress", missing, f"{STAGE_FILES[missing]} not written yet"


def schedule(cwd, backlog, tasks):
    """Print every story's state and the next one to run; return 0.

    One story with unfinished code at a time: a story past its plan stage that is not delivered
    holds the checkout, because its tests and code are in the working tree and a second story
    would build on them. Such a story is next if it can run, and nothing else starts while it
    cannot. A story that stopped at its plan stage wrote no code, so independent work runs past it."""
    stories, order = {}, []
    for root, _dirs, files in os.walk(backlog):
        for name in sorted(files):
            if not name.endswith(".md") or name == "epic.md":
                continue
            path = os.path.join(root, name)
            try:
                front, _body = read_front_matter(path)
            except GateError as error:
                stories[name[:-3]] = dict(state="stopped", start=None, detail=str(error), deps=[])
                continue
            story_id = str(front.get("id") or name[:-3]).strip()
            state, start, detail = story_state(cwd, tasks, story_id, front)
            stories[story_id] = dict(state=state, start=start, detail=detail, deps=depends_on(front),
                                     holds=state != "delivered" and os.path.isfile(
                                         os.path.join(tasks, story_id, STAGE_FILES["test"])))

    # dependency order, ties by id; whatever is left after that sits on a cycle
    placed, remaining = set(), sorted(stories)
    while remaining:
        free = [s for s in remaining if all(d in placed or d not in stories for d in stories[s]["deps"])]
        if not free:
            break
        order.append(free[0])
        placed.add(free[0])
        remaining.remove(free[0])
    for story_id in remaining:
        order.append(story_id)
    for story_id in order:
        story = stories[story_id]
        if story["state"] not in RUNNABLE:
            continue
        unknown = [d for d in story["deps"] if d not in stories]
        if story_id in remaining:
            story.update(state="blocked", start=None, detail="on a dependency cycle: "
                         + ", ".join(sorted(s for s in remaining)))
        elif unknown:
            story.update(state="blocked", start=None, detail="depends on unknown " + ", ".join(unknown))
        else:
            pending = [d for d in story["deps"] if stories[d]["state"] != "delivered"]
            if pending:
                story.update(state="blocked", start=None, detail="depends on " + ", ".join(
                    f"{d} ({stories[d]['state']})" for d in pending))

    holders = [s for s in order if stories[s].get("holds")]
    nxt, reason, wait = None, "", False
    if holders:
        holder = stories[holders[0]]
        if holder["state"] in RUNNABLE:
            nxt = holders[0]
        else:
            reason = (f"{holders[0]} holds unfinished code in the checkout ({holder['state']}) — "
                      f"no other story starts until it is delivered")
            wait = holder["state"] == "waiting"
    else:
        nxt = next((s for s in order if stories[s]["state"] in RUNNABLE), None)
        wait = any(stories[s]["state"] == "waiting" for s in order)
        if nxt is None:
            reason = "nothing can run"

    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        print(f"{story_id}  {story['state']:<11} {start:<13} {story['detail']}".rstrip())
    counts = {}
    for story in stories.values():
        counts[story["state"]] = counts.get(story["state"], 0) + 1
    print("schedule: " + (", ".join(f"{n} {state}" for state, n in sorted(counts.items()))
                          or "no story under " + backlog + "/"))
    print(f"wait: {'yes' if wait else 'no'}")
    print(f"next: {nxt} {stories[nxt]['start']}" if nxt else f"next: none — {reason}")
    return 0


class Result:
    def __init__(self):
        self.entries = []

    def ok(self, check, message):
        self.entries.append(("pass", check, message))

    def fail(self, check, message):
        self.entries.append(("fail", check, message))

    def skip(self, check, message):
        self.entries.append(("skip", check, message))

    def note(self, check, message):
        """A fact worth reading that fails nothing and covers nothing — it is not a skipped check."""
        self.entries.append(("note", check, message))

    @property
    def failed(self):
        return any(state == "fail" for state, _, _ in self.entries)

    def report(self, story_id, stage, as_json):
        for state, check, message in self.entries:
            print(f"gate:{state} {check} — {message}")
        skipped = [check for state, check, _ in self.entries if state == "skip"]
        if skipped:
            print(
                f"gate:note stage {stage} ran without {', '.join(sorted(set(skipped)))} — "
                f"a green run here does not cover them"
            )
        verdict = "fail" if self.failed else "pass"
        print(f"gate:{verdict} {stage}" if story_id == stage else f"gate:{verdict} story {story_id} stage {stage}")
        if as_json:
            print(
                json.dumps(
                    {
                        "story": story_id,
                        "stage": stage,
                        "verdict": verdict,
                        "checks": [
                            {"state": s, "check": c, "message": m}
                            for s, c, m in self.entries
                        ],
                    },
                    indent=2,
                )
            )
        return 1 if self.failed else 0


def resolve_profile(given, cwd):
    if given:
        return given
    for candidate in (
        os.path.join(".agents", "factory", "factory.profile.yaml"),
        "factory.profile.yaml",
    ):
        if os.path.isfile(os.path.join(cwd, candidate)):
            return candidate
    return None


def main(argv):
    parser = argparse.ArgumentParser(add_help=True, description="story gate")
    parser.add_argument(
        "--version", action="version",
        version=f"story-gate {VERSION} (file contract {CONTRACT})",
    )
    parser.add_argument("--story")
    parser.add_argument(
        "--stage",
        choices=("plan", "test", "build", "tidy", "document"),
    )
    parser.add_argument("--list-decisions", action="store_true",
                        help="print the decision inbox (all stories, or --story's) and exit")
    parser.add_argument("--change", action="store_true",
                        help="run the profile's checks outside a story and exit")
    parser.add_argument("--staged", action="store_true",
                        help="with --change: check the Git index, refuse when the working tree differs")
    parser.add_argument("--checks", help="with --change: only these checks (compile test architecture format)")
    parser.add_argument("--parity", metavar="CONFIG",
                        help="check every implementation's reports against a scenario contract and exit")
    parser.add_argument("--schedule", action="store_true",
                        help="print every story's state and the next one to run, and exit")
    parser.add_argument("--backlog", default="backlog")
    parser.add_argument("--tasks", default="tasks")
    parser.add_argument("--profile")
    parser.add_argument("--project", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.project)
    os.chdir(cwd)
    if args.list_decisions:
        return list_decisions(cwd, args.story)
    if args.schedule:
        return schedule(cwd, args.backlog, args.tasks)
    if args.change or args.parity:
        result, label = Result(), "change" if args.change else "parity"
        try:
            if args.change:
                profile = read_profile(resolve_profile(args.profile, cwd))
                check_contract(result, profile)
                change_check(result, cwd, profile, args.staged, args.checks)
            else:
                parity(result, args.parity)
        except GateError as error:
            result.fail("gate", str(error))
        return result.report(label, label, args.json)
    if not args.story or not args.stage:
        parser.error("--story and --stage are required (or --list-decisions, --schedule, --change, --parity)")
    result = Result()
    try:
        story_path = find_story(args.backlog, args.story)
        front, body = read_front_matter(story_path)
        story_id = str(front.get("id") or os.path.splitext(os.path.basename(story_path))[0])
        criteria = criteria_of(story_path, body)
        if not str(front.get("context", "")).strip():
            result.fail(
                "story",
                f"{story_path}: front matter has no `context:` — a story names the "
                f"bounded context it changes",
            )
        else:
            result.ok(
                "story",
                f"{story_id} in context {front['context']} with "
                f"{len(criteria)} criterion(s)",
            )
        profile = read_profile(resolve_profile(args.profile, cwd))
        check_contract(result, profile)
        check_status(result, story_path, front)
        check_epic(result, story_path, front, args.backlog)
        check_rounds(result, args.tasks, story_id)
        check_decisions(result, args.tasks, story_id, cwd, args.stage)
        if args.stage == "plan":
            check_context_map(
                result, cwd, profile, str(front.get("context", "")).strip()
            )
            check_instruction_size(result, cwd)
        if args.stage == "document":
            check_documented(result, args.tasks, story_id, cwd)
            check_proposals_landed(result, args.tasks, story_id, cwd, profile)
            check_stage_commands(result, profile, cwd, args.stage)
        if args.stage in ("test", "build", "tidy"):
            mapping = check_mapping(result, args.tasks, story_id, criteria)
            located = check_exists(result, cwd, mapping)
            check_compiles(result, profile, cwd)
            check_test_state(
                result,
                profile,
                cwd,
                mapping,
                "red" if args.stage == "test" else "green",
                located,
                args.tasks,
                story_id,
            )
            if args.stage in ("build", "tidy"):
                check_required_suites(result, profile, cwd)
            check_stage_commands(result, profile, cwd, args.stage)
    except GateError as error:
        result.fail("gate", str(error))
        return result.report(args.story, args.stage, args.json)
    return result.report(story_id, args.stage, args.json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
