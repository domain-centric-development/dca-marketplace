#!/usr/bin/env python3
"""Story gate — the deterministic part of a factory run.

Reads the backlog (markdown with front matter) and the stack profile, then checks
what a stage may not decide for itself. Exit code 0 means the stage may proceed.

    story-gate.py --story <id> --stage <plan|test|build|document> [options]

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
           plus every extra check the profile declares for this stage (architecture suite,
           formatter, …). Without the record the green run is skipped and named, never taken as
           evidence: a runner that matched no test at all exits 0 exactly like a passing one
    tidy   the same as build: nothing the refactor touched may have changed what the code does
    document  every path, file and identifier the document stage claims actually exists, every
           row of its glossary table names where its definition came from, and every term the plan
           proposed has landed in a glossary

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import json
import os
import re
import glob
import hashlib
import subprocess
import sys
import time
from xml.etree import ElementTree

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
    missing test looks exactly like a red one, and the run would certify nothing."""
    if not mapping:
        return
    sources = {}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [
            d
            for d in dirs
            if d not in ("build", "out", "bin", "obj", "target", "node_modules", ".git")
        ]
        for name in files:
            sources.setdefault(os.path.splitext(name)[0], []).append(
                os.path.join(root, name)
            )
    located = {}
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            cls, method = SELECTOR.match(selector).groups()
            simple = cls.rsplit(".", 1)[-1]
            candidates = sources.get(simple, [])
            found = [path for path in candidates if contains(path, method)]
            if found:
                located[selector] = os.path.relpath(found[0], cwd)
                result.ok(
                    "tests-exist",
                    f"{selector} found in {located[selector]} ({key})",
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


def run(command, cwd):
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
    if "## needs-human" in text:
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
#: A selector no project can contain — the control run's subject (see `discriminates`).
SENTINEL = ("dev.dca.factory.NoSuchTestClass", "noSuchTestMethod")
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


def executed_tests(paths):
    """{(class, method): outcome} for every test a report says ran. Outcome is 'passed' or 'failed'.

    Two formats, because two are enough to cover the runners this is used with. A report is the
    only artefact that states what was *executed*: an exit code says how a process ended, and a
    message says what a process printed — neither says a test ran.
    """
    ran = {}
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
                    ran[(cls, method.split("(")[0])] = outcome
            elif tag == "UnitTestResult":                           # TRX
                name = (case.get("testName") or "").strip()
                outcome = (case.get("outcome") or "").strip().lower()
                if name:
                    cls, _, method = name.rpartition(".")
                    ran[(cls, method.split("(")[0])] = (
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
    in_class = [(m, o) for (report_class, m), o in ran.items() if same_class(report_class)]
    if not in_class:
        return None, ""
    if len(in_class) == 1:
        # The run was filtered to this one selector and the report holds exactly one case for its
        # class: that case is this test, whatever name the runner chose to print.
        return in_class[0][1], "by class — the filtered run reported exactly one case for it"
    # Several cases: attributing any one of them to this selector would let another method's result
    # decide this criterion. No mapping, no verdict.
    return None, (f"the report holds {len(in_class)} cases for that class "
                  f"({', '.join(sorted(name for name, _ in in_class)[:4])}) and none is named "
                  f"{method!r}")


def discriminates(command, flag, fmt, cwd, cache):
    """(control_code, control_output) for this command, run once and remembered.

    Only used where a project has opted out of report evidence: comparing a real run against a run
    with a selector that cannot exist is weaker — a runner that prints the selector back in its
    "no tests found" line answers differently without having run anything.
    """
    if command not in cache:
        pattern = fmt.replace("{class}", SENTINEL[0]).replace("{method}", SENTINEL[1])
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
            pattern = fmt.replace("{class}", cls).replace("{method}", method)
            test_path = located.get(selector)
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
                    f"before the code exists proves nothing about {key!r}.",
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
        print(f"gate:{verdict} story {story_id} stage {stage}")
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
    parser.add_argument("--story", required=True)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("plan", "test", "build", "tidy", "document"),
    )
    parser.add_argument("--backlog", default="backlog")
    parser.add_argument("--tasks", default="tasks")
    parser.add_argument("--profile")
    parser.add_argument("--project", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.project)
    os.chdir(cwd)
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
        check_status(result, story_path, front)
        check_epic(result, story_path, front, args.backlog)
        check_rounds(result, args.tasks, story_id)
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
            check_stage_commands(result, profile, cwd, args.stage)
    except GateError as error:
        result.fail("gate", str(error))
        return result.report(args.story, args.stage, args.json)
    return result.report(story_id, args.stage, args.json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
