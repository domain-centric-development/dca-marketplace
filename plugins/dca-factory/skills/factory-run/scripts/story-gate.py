#!/usr/bin/env python3
"""Story gate — the deterministic part of a factory run.

Reads the backlog (markdown with front matter) and the stack profile, then checks
what a stage may not decide for itself. Exit code 0 means the stage may proceed.

    story-gate.py --story <id> --stage <plan|test|build|tidy|document> [options]
    story-gate.py --list-decisions [--story <id>]      the decision inbox, one line per record
    story-gate.py --schedule                           every story's state and the next one to run
    story-gate.py --check-backlog                      the plan gate's backlog checks over every story
                                                       that is not done; exit 1 when one is refused
    story-gate.py --usage [--story <id>] [--total]     tokens per story and stage, from the journals
    story-gate.py --project                            the project description (product and technical)
                                                       alone; exit 3 while a part is missing, 1 when
                                                       one is incomplete
    story-gate.py --status [--story <id>]              what runs, what waits, every story, the cost —
                                                       per story, or per stage of --story
    story-gate.py --change [--staged] [--checks <c>]   the profile's checks outside a story; --staged
                                                       checks what the commit contains (the hook, CI)
    story-gate.py --parity <config>                    every implementation's reports prove every
                                                       mandatory scenario of a scenario contract

Options:
    --backlog <dir>     backlog root (default: the profile's `backlog:`, else project/backlog)
    --root <dir>        the project's root (default: .)
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
    test, build, tidy  a test file that existed before the story (recorded by the plan gate) still
           holds every line it had; a changed or removed one needs an answered decision of stage test
    every stage  the story's decision records under .agents/factory/decisions/: a `## needs-human`
           section names one, an open one stops the story, an answered one is applied by the
           stage that asked and then stamped `## Applied` here

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import contextlib
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
    "project/domain.md",
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
#: The project description: what is to be built, written before the code and read as a story's input.
#: `project/` unless the profile names another place — the files a person writes, apart from what the
#: machine keeps under `.agents/factory/` and the stages' hand-overs under `tasks/`.
DEFAULTS = {
    "product": "project/product.md",
    "tech": "project/tech.md",
    "domain": "project/domain.md",
    "backlog": "project/backlog",
}
#: The product description's headings — what is built, for whom, through which surfaces.
PRODUCT_HEADINGS = (
    "What and for whom",
    "Surfaces",
    "How it works",
    "Look and feel",
    "Qualities",
    "Not part of the product",
)
#: The technical description's headings — the decisions a stage may not take in passing.
TECH_HEADINGS = (
    "Stack",
    "Frontend approach",
    "Persistence",
    "Runtime",
    "Integrations",
    "Version policy",
)
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
CONTRACT = 7
VERSION = "0.33.4"


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
        # `key: ""` is YAML for an empty string: read quoted, it would count as a filled field.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
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
        f"{backlog}/<epic>/<story>.md with front matter (see the backlog contract)"
    )


STEP = re.compile(r"^-\s+(Given|When|Then|And|But)\b\s*(.*)$")
SCENARIO_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def criteria_of(story_path, body):
    """Acceptance criteria as (key, text) pairs, read from the `## Acceptance criteria` section.

    Two forms, mixable. The line form: one `- <key>: <text>` line per criterion. The scenario form:
    `#### <key>` followed by `- Given / When / Then / And / But` steps, optionally grouped under
    `### Rule: <text>` headings — Gherkin's own shape. The key is a name, never a number, and is
    what the test stage binds. The shape is checked here, deterministically: a rule without a
    scenario, a scenario without exactly one trigger or without an outcome, a step outside a
    scenario, an unknown step and a repeated key are refused. Whether a scenario covers its rule
    is not a question a script can answer; the backlog skill asks it."""
    collecting, found, keys = False, [], set()
    rule, rule_scenarios, scenario = None, 0, None

    def refuse(message):
        raise GateError(f"{story_path}: {message}")

    def close_scenario():
        nonlocal scenario
        if scenario is None:
            return
        key, steps = scenario
        triggers, outcome, phase = 0, False, None
        for word, _ in steps:
            if word in ("Given", "When", "Then"):
                phase = word
            if word == "When" or (word in ("And", "But") and phase == "When"):
                triggers += 1
            if word == "Then":
                outcome = True
        if not steps:
            refuse(f"scenario `{key}` has no steps — write `- Given / When / Then` lines under it")
        if triggers != 1:
            refuse(f"scenario `{key}` has {triggers} triggers — exactly one `When` (an `And` after it is "
                   f"a second trigger); two triggers are two scenarios")
        if not outcome:
            refuse(f"scenario `{key}` has no `Then` — a scenario states what is observed")
        found.append((key, "; ".join(f"{word} {text}".strip() for word, text in steps)))
        scenario = None

    def close_rule():
        if rule is not None and rule_scenarios == 0:
            refuse(f"rule `{rule}` has no scenario — every rule gets at least one `#### <key>` scenario")

    def add_key(key):
        if key in keys:
            refuse(f"acceptance criterion key `{key}` appears twice — a key names one behaviour")
        keys.add(key)

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting or not stripped:
            continue
        if line.startswith("### "):
            close_scenario()
            close_rule()
            heading = line[4:].strip()
            if not heading.lower().startswith("rule:"):
                refuse(f"`### {heading}` — a third-level heading under the criteria is a `### Rule: <text>`")
            rule, rule_scenarios = heading[5:].strip(), 0
            continue
        if line.startswith("#### "):
            close_scenario()
            key = line[5:].strip()
            if not SCENARIO_KEY.match(key):
                refuse(f"scenario heading `#### {key}` is not a key — lowercase and hyphenated, naming the behaviour")
            add_key(key)
            scenario = (key, [])
            if rule is not None:
                rule_scenarios += 1
            continue
        step = STEP.match(stripped)
        if step:
            if scenario is None:
                refuse(f"step {stripped!r} stands outside a scenario — put it under a `#### <key>` heading")
            scenario[1].append((step.group(1), step.group(2).strip()))
            continue
        if scenario is not None and stripped.startswith("-"):
            refuse(f"scenario `{scenario[0]}`: {stripped!r} is not a step — steps begin with Given, When, "
                   f"Then, And or But")
        match = CRITERION.match(stripped)
        if match:
            close_scenario()
            add_key(match.group(1))
            found.append((match.group(1), match.group(2).strip()))
        elif stripped.startswith("-"):
            refuse(f"acceptance criterion {stripped!r} has no key — write `- <key>: <criterion>` with a "
                   f"lowercase, hyphenated key that names the behaviour, or a `#### <key>` scenario")
    close_scenario()
    close_rule()
    if not found:
        raise GateError(
            f"{story_path}: no acceptance criteria — add a `## Acceptance criteria` "
            f"section with one `- <key>: <criterion>` line or one `#### <key>` scenario per criterion"
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
            f"{CONTRACT} (gate {VERSION}) — run `factory.sh update` before trusting a run, "
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
    """A story names the context it changes; that context must be on the map. The designed map
    (`domain:`) is read first, so a story for a context that is designed but not built yet passes;
    then the one generated from the code (`contextMap:`), then the conventional places. A project
    without a map is not blocked — it has nothing to contradict yet."""
    named_domain = str(profile.get("domain", "")).strip()
    if named_domain and not os.path.isfile(os.path.join(cwd, named_domain)):
        result.fail("context-map", f"the profile's `domain: {named_domain}` names no file")
        return
    candidates = [location(profile, "domain")]
    named = profile.get("contextMap")
    if named and os.path.isfile(os.path.join(cwd, named)):
        candidates.append(named)
    path = find_first(cwd, candidates + list(CONTEXT_MAP_CANDIDATES))
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


MODEL_TOOLS = ("claude", "codex", "opencode")


def check_models(result, profile):
    """`model.<tool>.<stage>` and `model.<tool>`: the model a tool runs a stage on. The key names the tool
    because model names are the tool's: a profile is checked in and shared, and an unqualified
    `model.tidy: <a model name>` would break a colleague's run with another tool at the first stage it names.
    So the unqualified forms are refused, and so is a key whose tool or stage is misspelled — an
    ignored key is a cost saving nobody gets while everyone believes in it."""
    keys = [key for key in profile if key == "model" or key.startswith("model.")]
    if not keys:
        return
    bad = []
    for key in keys:
        parts = key.split(".")
        if len(parts) == 1 or (len(parts) == 2 and parts[1] in STAGE_ORDER):
            bad.append(f"`{key}` names no tool — write `model.<tool>.<stage>` or `model.<tool>` "
                       f"({', '.join(MODEL_TOOLS)})")
        elif parts[1] not in MODEL_TOOLS:
            bad.append(f"`{key}`: no tool `{parts[1]}` ({', '.join(MODEL_TOOLS)})")
        elif len(parts) == 3 and parts[2] not in STAGE_ORDER:
            bad.append(f"`{key}`: no stage `{parts[2]}` ({', '.join(STAGE_ORDER)})")
        elif len(parts) > 3:
            bad.append(f"`{key}` is not `model.<tool>.<stage>`")
        elif not str(profile[key]).strip():
            bad.append(f"`{key}` has no value")
    if bad:
        result.fail("models", "; ".join(bad))
    else:
        result.ok("models", f"{len(keys)} model key(s), each bound to a tool")


def location(profile, key):
    """Where the profile puts one part of the project description, or its default under `project/`."""
    return str(profile.get(key, "")).strip().replace("\\", "/") or DEFAULTS[key]


def layout_hint(cwd, profile):
    """The layout before `project/`: a backlog at the root. No fallback reads it; the move is named."""
    if os.path.isdir(os.path.join(cwd, "project")) or profile.get("backlog"):
        return None
    moves = []
    if os.path.isfile(os.path.join(cwd, "backlog", "product.md")):
        moves.append("git mv backlog/product.md project/product.md")
    if os.path.isdir(os.path.join(cwd, "backlog")):
        moves.append("git mv backlog project/backlog")
    if not moves:
        return None
    return ("the backlog now lives under project/ — mkdir -p project && " + " && ".join(moves)
            + ", then `contract: 7` in the profile")


def check_described(result, cwd, profile, key, headings, what):
    """One part of the project description. Absent is a note — the gate does not block a project
    that has none, the backlog skill does. A key that names a missing file is a broken reference,
    and a heading missing or empty is a description nobody finished: both fail. Guidance in HTML
    comments does not count as content, so an untouched template does not pass."""
    named = str(profile.get(key, "")).strip()
    path = location(profile, key)
    full = os.path.join(cwd, path)
    if not os.path.isfile(full):
        if named:
            result.fail(key, f"the profile's `{key}: {named}` names no file")
        else:
            result.note(key, f"no {what} at {path} — `/factory-setup` writes it before the first story")
        return False
    text = re.sub(r"<!--.*?-->", "", read_text(full), flags=re.S)
    sections, current = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    missing = [h for h in headings if h.lower() not in sections]
    empty = [h for h in headings if h.lower() in sections and not "".join(sections[h.lower()]).strip()]
    if missing or empty:
        detail = "; ".join(filter(None, [
            f"missing `## {'`, `## '.join(missing)}`" if missing else "",
            f"empty `## {'`, `## '.join(empty)}`" if empty else "",
        ]))
        result.fail(key, f"{path}: {detail} — every heading gets one honest line, never a placeholder")
        return False
    result.ok(key, f"{path} fills all {len(headings)} headings of the {what}")
    return True


def check_project(result, cwd, profile):
    """The two mandatory parts of the project description: the product and the technical decisions.
    The designed context map (`domain:`) is read by the context check and stays optional here."""
    product = check_described(result, cwd, profile, "product", PRODUCT_HEADINGS, "product description")
    tech = check_described(result, cwd, profile, "tech", TECH_HEADINGS, "technical description")
    return product and tech


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


def check_backlog(cwd, backlog, tasks, profile, only=None):
    """The plan gate's backlog checks over every story that is not done, or over `only`: front
    matter, the epic's completeness, the criteria, the status and the context on the map. Nothing of
    its own — the same functions the plan gate calls, so a story that passes here passes there on
    these points. A draft is a story still being written, named and not refused. It writes nothing:
    the plan gate's marks (the story digest, the tests baseline) belong to the run that plans the
    story, and a baseline taken while the story is still being written would be the wrong one."""
    checked, refused = 0, []
    if layout_hint(cwd, profile):
        print(f"gate:note layout — {layout_hint(cwd, profile)}")
    for root, _dirs, files in sorted(os.walk(backlog)):
        if os.path.normpath(root) == os.path.normpath(backlog):
            continue
        for name in sorted(files):
            if not name.endswith(".md") or name == "epic.md":
                continue
            path = os.path.join(root, name)
            result, label = Result(), name[:-3]
            try:
                front, body = read_front_matter(path)
                label = str(front.get("id") or label).strip()
                if only and only not in (label, name[:-3]):
                    continue
                status = str(front.get("status", "")).strip().lower()
                if status == "superseded" or os.path.isfile(os.path.join(tasks, label, DELIVERED)):
                    continue
                if status == "draft":
                    result.note("approved", f"{path}: a draft — released with `status: approved` once it is written")
                elif status and status != "approved":
                    result.fail("approved", f"{path}: status {status!r} is none of draft, approved, superseded")
                context = str(front.get("context", "")).strip()
                if not context:
                    result.fail("story", f"{path}: front matter has no `context:` — a story names the bounded "
                                         f"context it changes")
                criteria = criteria_of(path, body)
                if context:
                    result.ok("story", f"{label} in context {context} with {len(criteria)} criterion(s)")
                    check_context_map(result, cwd, profile, context)
                check_epic(result, path, front, backlog)
            except GateError as error:
                result.fail("story", str(error))
            checked += 1
            for state, check, message in result.entries:
                if state != "pass":
                    print(f"gate:{state} {label} {check} — {message}")
            if result.failed:
                refused.append(label)
    if not checked:
        if only:
            print(f"backlog: no story {only} to check under {backlog}/ (not there, delivered or superseded)")
            return 1
        print(f"backlog: no story to check under {backlog}/")
        return 0
    print(f"backlog: {checked} story(ies) checked" + (f", refused: {', '.join(refused)}" if refused
                                                     else " — every one holds for the plan gate"))
    return 1 if refused else 0


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
            [bash, "-c", command], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        return completed.returncode, completed.stdout + completed.stderr
    completed = subprocess.run(
        command, cwd=cwd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
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


def unescape_literal(text):
    """A Java or C# string literal's content as the runtime sees it: `\\"` is `"`, `\\\\` is `\\`.
    A report carries the name unescaped, so a title with a quote in it would otherwise never match."""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), text)


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
                        return unescape_literal(match.group(1))
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
    # An expectation that changes on a human's decision: the test was recorded red before the code
    # existed, the decision changed what it expects, and the code now meets it. Only that combination
    # lets a green test through the red check — without the decision it is the refusal below.
    changed_on = answered_decisions(cwd, story, "test") if expected == "red" else []
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
            if expected == "red" and passed and selector in was_red and changed_on:
                now_red.add(selector)
                result.ok("tests-red", f"{selector} is green now and was recorded red before; its "
                                       f"expectation changed on decision {', '.join(changed_on)} ({key})")
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
        write_red_ledger(tasks, story, now_red, located, cwd)
    elif have_ledger:
        check_red_proof(result, cwd, located, read_red_digests(tasks, story), story)


def check_red_proof(result, cwd, located, digests, story):
    """At build and tidy: every test's red proof was taken against the test as it is now."""
    unbound = [s for s, d in digests.items() if d is None]
    if unbound and len(unbound) == len(digests):
        result.skip("red-proof", "the red record names no test-file digests (written by an older gate) — "
                                 "whether a test changed since it was seen failing is not checked")
        return
    moved = []
    for selector, digest in sorted(digests.items()):
        test_file = located.get(selector)
        if not digest or not test_file or not os.path.isfile(os.path.join(cwd, test_file)):
            continue
        if file_digest(os.path.join(cwd, test_file)) != digest:
            moved.append(f"{selector} ({test_file})")
    if not moved:
        result.ok("red-proof", f"{len(digests) - len(unbound)} test(s) are the version that was seen failing")
    elif answered_decisions(cwd, story, "test"):
        result.ok("red-proof", f"{', '.join(moved)} changed after it was seen failing, on decision "
                               f"{', '.join(answered_decisions(cwd, story, 'test'))}")
    else:
        result.fail(
            "red-proof",
            f"{', '.join(moved)} changed after the test stage saw it fail — the red proof is about the "
            f"earlier version, so its green now proves nothing. The test stage runs again and records "
            f"it red as it is; a change of what it expects is a human's decision.",
        )


#: Which selectors the test stage saw fail. Kept as a file next to the round counter for the same
#: reason: the build gate must not take a stage's word that a test was red once.
def red_ledger_path(tasks, story):
    if not tasks or not story:
        return None
    return os.path.join(tasks, story, ".tests-red")


def read_red_digests(tasks, story):
    """{selector: sha256 of its test file when it was recorded red, or None for an older ledger}.

    A red proof is a proof about one version of a test. The digest binds it to that version, so a
    test weakened after it was seen failing no longer carries the proof into the build gate."""
    path = red_ledger_path(tasks, story)
    if not path or not os.path.isfile(path):
        return {}
    digests = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            selector, _, digest = line.strip().partition("\t")
            if selector:
                digests[selector] = digest.strip() or None
    return digests


def read_red_ledger(tasks, story):
    return set(read_red_digests(tasks, story))


def write_red_ledger(tasks, story, selectors, located=None, cwd="."):
    path = red_ledger_path(tasks, story)
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    for selector in sorted(selectors):
        test_file = (located or {}).get(selector)
        full = os.path.join(cwd, test_file) if test_file else None
        lines.append(f"{selector}\t{file_digest(full)}" if full and os.path.isfile(full) else selector)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + ("\n" if lines else ""))


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


def answered_decisions(cwd, story_id, stage):
    """Ids of this story's answered or applied records whose `stage:` is the given stage."""
    try:
        records = read_decisions(os.path.join(cwd, DECISIONS_DIR), story_id)
    except GateError:
        return []
    return [str(front["id"]).strip() for _p, front, _b, state, _a in records
            if state in ("answered", "applied") and str(front.get("stage", "")).strip() == stage]


def nothing_line(line):
    """`(none)`, `- None.`, `_None._`, `—` and the like: a line that says there is nothing."""
    text = line.strip().lstrip("-*").strip().strip("_*()").strip().rstrip(".").strip()
    return text.lower() in NOTHING


def needs_human_ids(text):
    """The decision ids a `## needs-human` section names (`decision: <id>`), or [] without one;
    None when the file has no such section at all — or only the heading, left empty or filled with
    `(none)` from the file template: that asks nobody anything, and reading it as a stop halts a
    finished stage."""
    section = section_of(text, "needs-human")
    if section is None or all(nothing_line(line) for line in section):
        return None
    return [value for key, value in fields_of(section).items() if key == "decision" and value]


def stamp_applied(path, stage):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"\n## Applied\nat: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                     f"stage: {stage}\n")


def decision_files(cwd):
    """(id from the file name, front, body, state, error) for every record in the store, sorted by name."""
    store = os.path.join(cwd, DECISIONS_DIR)
    if not os.path.isdir(store):
        return
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        try:
            front, body = read_front_matter(os.path.join(store, name))
        except GateError as error:
            yield name[:-3], {}, "", "unreadable", error
            continue
        yield name[:-3], front, body, decision_state(body)[0], None


def list_decisions(cwd, story_id=None):
    """The inbox: one line per record, open ones first, then drafts, answered, applied.

    `<id>  <state>  <story>/<stage>  asked <time>  <question>` — what a second session needs to
    pick one up without any transcript. Read from the files alone; nothing is inferred."""
    rows = []
    for name, front, body, state, error in decision_files(cwd):
        if error:
            rows.append((-1, name, "unreadable", "?", "?", "?", str(error)))
            continue
        story = str(front.get("story", "")).strip()
        if story_id and story != story_id:
            continue
        answer = decision_state(body)[1]
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        rank = {"open": 0, "draft": 1, "answered": 2, "applied": 3}[state]
        rows.append((rank, str(front.get("id", name)).strip(), state, story,
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
            # Before the plan stage runs, an answer it has to apply is its input — also one a judge's
            # story conflict routed here, which the plan written before the conflict cannot cite yet.
            if gating == "plan" and stage == "plan" and (text is None or still_asking or rid not in text):
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
        # UTF-8, not the locale: on Windows a cp1252 reading turns an umlaut into another character (a
        # test that did not change looks changed) and raises on bytes like 0x81.
        completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env,
                                   encoding="utf-8", errors="replace")
    except OSError as error:
        return 1, str(error)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def split_list(value):
    return [part for part in re.split(r"[\s,]+", str(value or "").strip()) if part]


TOOL_FOLDERS = ("/.claude/", "/.codex/", "/.opencode/")


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
    # The agent tools' own folders — skill links, a settings file the install wrote — are no input to
    # any check here, and refusing every commit over them would stop the first commit after an install.
    tooling = lambda p: any(folder in "/" + p for folder in TOOL_FOLDERS)
    drift = [f"modified, not staged: {p}" for p in unstaged.splitlines() if p and not tooling(p)] \
        + [f"untracked: {p}" for p in untracked.splitlines() if p and not tooling(p)]
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


# --- existing tests keep their expectations -------------------------------------

# A story may add tests and add cases to a test file; it may not change what a test that existed
# before it expects, unless a human decided that. The plan gate runs before any stage of the story
# touches a test, so it records the test files as git blobs; later gates compare against them.
TESTS_BASELINE = ".tests-baseline"
TEST_FILE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go|rb|exs?)$|Tests?\.(java|kt|cs|scala|groovy)$|IT\.(java|kt)$"
    r"|Spec\.(scala|groovy|kt)$|\.(test|spec)\.(js|jsx|ts|tsx|mjs)$|_spec\.rb$)")
SKIP_DIRS = {".git", "build", "target", "bin", "obj", "node_modules", "dist", ".gradle", "tasks",
             ".agents", ".claude", ".codex", ".opencode", "__pycache__", ".venv", "venv"}


def test_files(cwd):
    found = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


def record_tests_baseline(cwd, tasks, story_id):
    """Write the baseline once per story; a later plan gate must not launder a change into it."""
    path = os.path.join(tasks, story_id, TESTS_BASELINE)
    if os.path.isfile(path) or git(cwd, "rev-parse", "--git-dir")[0]:
        return
    files = test_files(cwd)
    blobs = []
    for rel in files:
        code, blob = git(cwd, "hash-object", "-w", "--", rel)
        if code == 0:
            blobs.append(f"{blob}  {rel}")
    write_mark(tasks, story_id, TESTS_BASELINE, "\n".join(blobs))


def human_line(text):
    """A line a person wrote: not empty, not "none", not a template placeholder or an HTML comment."""
    text = re.sub(r"<!--.*?-->", "", text).strip()
    return bool(text) and text.lower() not in NOTHING and "{{" not in text


def changed_tests_in_plan(tasks, story_id):
    """{test file: backed-by cell} from the plan's `## Changed tests` table."""
    path = os.path.join(tasks, story_id, "plan.md")
    rows = {}
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


def meaningful_lines(text, path):
    if path.endswith(HASH_COMMENTS):
        text = TRIPLE_QUOTED.sub("", text)
        lines = [re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines()]
    else:
        text = DISABLED_BLOCK.sub("", BLOCK_COMMENT.sub("", text))
        lines = [re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines()]
    return [line.rstrip() for line in lines if line.strip()]


def switched_off(before, now):
    """Whether the new version carries more skip markers than the old one."""
    count = lambda lines: sum(1 for line in lines if SKIP_MARKER.search(line))
    return count(now) > count(before)


def check_existing_tests(result, cwd, tasks, story_id, story_body=""):
    path = os.path.join(tasks, story_id, TESTS_BASELINE)
    if not os.path.isfile(path):
        result.skip("tests-kept", "no baseline of the tests that existed before this story "
                                  "(the plan gate records one in a git repository)")
        return
    changed, lost = [], []
    for line in read_text(path).splitlines():
        if "  " not in line:
            continue
        blob, rel = line.split("  ", 1)
        full = os.path.join(cwd, rel)
        if not os.path.isfile(full):
            changed.append(f"{rel} (removed)")
            continue
        code, before = git(cwd, "cat-file", "blob", blob)
        if code:
            lost.append(rel)
            continue
        with open(full, encoding="utf-8", errors="replace") as handle:
            now = meaningful_lines(handle.read(), rel)
        was = meaningful_lines(before, rel)
        # Additions only: every line the test had is still there, in the same order, outside a comment
        # — and no added line switches it off.
        remaining = iter(now)
        if not all(any(old == new for new in remaining) for old in was):
            changed.append(rel)
        elif switched_off(was, now):
            changed.append(f"{rel} (switched off)")
    if lost:
        result.skip("tests-kept", f"the baseline of {', '.join(lost)} is gone from the object store (pruned by "
                                  f"`git gc`?) — not compared")
    if not changed:
        result.ok("tests-kept", "no test that existed before this story changed what it expects")
        return
    decided = answered_decisions(cwd, story_id, "test")
    if decided:
        result.ok("tests-kept", f"{', '.join(changed)} changed on decision {', '.join(decided)}")
        return
    # The story may say itself that behaviour changes (`## Changed expectations`); the plan names the
    # tests that change with it (`## Changed tests`), each backed by that section or by a decision a
    # human answered. Nobody has to know which story wrote a test — or whether a story did at all.
    # Only list items count: the template's instruction prose and its `{{…}}` placeholder are no
    # human's approval.
    story_says = [l for l in (section_of(story_body, "changed expectations") or [])
                  if l.strip().startswith(("-", "*")) and human_line(l.strip()[1:].strip())]
    try:
        answered = {str(front["id"]).strip() for _p, front, _b, state, _a in
                    read_decisions(os.path.join(cwd, DECISIONS_DIR), story_id) if state in ("answered", "applied")}
    except GateError:
        answered = set()
    listed = changed_tests_in_plan(tasks, story_id)
    backed, unbacked, unlisted = [], [], []
    for entry in changed:
        rel = entry.replace(" (removed)", "").replace(" (switched off)", "")
        if rel not in listed:
            unlisted.append(entry)
        elif story_says or any(rid in listed[rel] for rid in answered):
            backed.append(entry)
        else:
            unbacked.append(entry)
    if backed and not unbacked and not unlisted:
        result.ok("tests-kept", f"{', '.join(backed)} changed as the plan lists, backed by "
                                + ("the story's `## Changed expectations`" if story_says else "an answered decision"))
        return
    if unlisted:
        result.fail(
            "tests-kept",
            f"{', '.join(unlisted)} existed before this story and no longer expects what it did, and the "
            f"plan's `## Changed tests` does not list it. Keep the old lines and add a case — or, where the "
            f"story changes that behaviour, the plan lists the test with what backs the change.",
        )
    if unbacked:
        result.fail(
            "tests-kept",
            f"{', '.join(unbacked)} is listed under the plan's `## Changed tests`, but nothing a human "
            f"wrote backs it: the story has no `## Changed expectations`, and the row cites no answered "
            f"decision. The plan stage asks (one record listing the tests), and the row cites its id.",
        )


def check_required_suites(result, profile, cwd):
    """At build and tidy: the test commands the policy requires, run whole.

    The mapped tests say this story's behaviour holds; they say nothing about the behaviour the
    stories before it delivered. Without a policy the stage gates stay as they were."""
    required = set(split_list(profile.get("required")))
    if not required:
        return
    # A required test key without its command fails here as it does in `--change`: silently passed,
    # the stage gate would certify a suite nobody can run.
    wanted = sorted(set(test_command_keys(profile)) | {r for r in required if r == "e2eTest" or r.startswith("test.")})
    for key in wanted:
        if key in required and not profile.get(key):
            result.fail("suite", f"no `{key}:` command in the stack profile — and `{key}` is required")
    keys = [k for k in test_command_keys(profile) if k in required and profile.get(k)]
    if not keys and not any(k in required for k in wanted):
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
        result.note("policy", "the profile declares no `required:` — nothing is mandatory: what is declared "
                              "runs and fails when red, what is not is named")
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
    return scenarios


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
    # A scenario without its `Title:` line binds to no test: dropped, it would leave parity silently.
    untitled = [s["id"] for s in scenarios if not s["title"]]
    scenarios = [s for s in scenarios if s["title"]]
    if untitled:
        result.fail("contract", f"{', '.join(untitled)} in {config['scenarios']} carry no `Title:` line — "
                                f"the title is what binds a scenario to a test")
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


# --- usage ------------------------------------------------------------------------

# What a stage cost, as the tool itself reports it. The runner saves each invocation's raw output and
# asks this script to read it; the numbers land in the story's journal next to the stage's start and
# end, so they survive restarts, second sessions and new runs like everything else there. A tool that
# reports nothing is `unknown` — never zero, because a zero would look like a cheap stage.
USAGE_FIELDS = ("input", "cache_read", "cache_write", "output")


def parse_usage(fmt, path):
    """({model, input, cache_read, cache_write, output, cost} or None, the final message text)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return None, ""
    if fmt == "claude-json":
        try:
            data = json.loads(raw)
        except ValueError:
            return None, raw
        models = data.get("modelUsage") or {}
        if not models:
            return None, str(data.get("result", ""))
        usage = {"model": ",".join(sorted(models)),
                 "input": sum(int(m.get("inputTokens", 0)) for m in models.values()),
                 "cache_read": sum(int(m.get("cacheReadInputTokens", 0)) for m in models.values()),
                 "cache_write": sum(int(m.get("cacheCreationInputTokens", 0)) for m in models.values()),
                 "output": sum(int(m.get("outputTokens", 0)) for m in models.values())}
        if data.get("total_cost_usd") is not None:
            usage["cost"] = f"{float(data['total_cost_usd']):.4f}"
        return usage, str(data.get("result", ""))
    if fmt == "codex-jsonl":
        usage, seen, text = {k: 0 for k in USAGE_FIELDS}, False, ""
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                seen = True
                u = event["usage"]
                cached = int(u.get("cached_input_tokens", 0))
                usage["input"] += int(u.get("input_tokens", 0)) - cached       # input counts the cached part
                usage["cache_read"] += cached
                usage["cache_write"] += int(u.get("cache_write_input_tokens", 0))
                usage["output"] += int(u.get("output_tokens", 0))
            item = event.get("item") or {}
            if event.get("type") == "item.completed" and item.get("type") in ("agent_message", "assistant_message"):
                text = str(item.get("text", text))
        return (usage if seen else None), text
    if fmt == "opencode-json":
        # `opencode run --format json`: one event per line; every model step ends in a `step_finish`
        # whose part carries that step's tokens, and the answer arrives as `text` parts. A local model
        # has no price (cost 0), which is reported as no price rather than as free.
        usage, seen, text, cost = {k: 0 for k in USAGE_FIELDS}, False, [], 0.0
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            part = event.get("part") or {}
            if event.get("type") == "text" and part.get("text"):
                text.append(str(part["text"]))
            if event.get("type") == "step_finish" and isinstance(part.get("tokens"), dict):
                seen = True
                t = part["tokens"]
                cache = t.get("cache") or {}
                usage["input"] += int(t.get("input", 0) or 0)
                usage["cache_read"] += int(cache.get("read", 0) or 0)
                usage["cache_write"] += int(cache.get("write", 0) or 0)
                usage["output"] += int(t.get("output", 0) or 0) + int(t.get("reasoning", 0) or 0)
                cost += float(part.get("cost", 0) or 0)
        if seen and cost > 0:
            usage["cost"] = f"{cost:.4f}"
        return (usage if seen else None), "".join(text).strip()
    return None, raw


# --- usage from a session log: a stage run inside an interactive session -----------------------------

# In a session there is no process per stage to ask for its output. What there is, is the tool's own
# log of the session: Claude Code writes every model response with its usage (the same response once
# per content block, so it is counted once per message id), Codex writes running totals. A stage is
# the time between two marks the orchestrator sets. Both formats are the tools' internal ones and not
# a documented interface: whatever this cannot read is reported as unknown, never guessed.
from datetime import datetime, timezone


def parse_time(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def claude_session_logs(session_id=None):
    """The session's log and its subagents' logs, for CLAUDE_CODE_SESSION_ID or the given id."""
    session_id = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    # The id may come from the journal, which is a file in the project: as a glob pattern, `*` would
    # open every session's log.
    if not session_id or not re.fullmatch(r"[\w-]+", session_id):
        return []
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    main = glob.glob(os.path.join(home, "projects", "*", f"{session_id}.jsonl"))
    if not main:
        return []
    return main[:1] + sorted(glob.glob(os.path.join(os.path.dirname(main[0]), session_id, "subagents", "*.jsonl")))


def codex_session_log(session_id=None):
    """The Codex session log of CODEX_SESSION_ID (or the given id) — found by its file name, which ends
    in the id, so no other session's log is opened."""
    session_id = session_id or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID", "")
    if not session_id or not re.fullmatch(r"[\w-]+", session_id):
        return None
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    found = glob.glob(os.path.join(home, "sessions", "**", f"rollout-*{session_id}.jsonl"), recursive=True)
    return found[0] if found else None


def session_usage_allowed(cwd):
    """Reading a tool's session log can be switched off: per person (FACTORY_SESSION_USAGE=off) or for
    the project (`sessionUsage: off` in the stack profile). In-session stages are then unknown."""
    if os.environ.get("FACTORY_SESSION_USAGE", "").strip().lower() in ("off", "0", "no", "false"):
        return False
    profile = read_profile(resolve_profile(None, cwd))
    return str(profile.get("sessionUsage", "on")).strip().lower() not in ("off", "0", "no", "false")


def session_usage(kind, paths, start=None, end=None):
    """{model, input, cache_read, cache_write, output} over the window, or None when nothing is read."""
    def inside(stamp):
        return stamp is not None and (start is None or stamp >= start) and (end is None or stamp <= end)
    if kind == "claude-session":
        # One API response is written as several log entries — one per content block — that share its
        # message id. The entries repeat the input and cache counts, and the output count grows until
        # the last one: counting the first entry alone undercounts output many times over. So each
        # field is the largest any entry of that message states.
        seen, models, per_message = set(), set(), {}
        for path in paths:
            try:
                handle = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    message = entry.get("message")
                    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict) \
                            or str(message.get("model", "")).startswith("<"):   # `<synthetic>`: no model call
                        continue
                    key = message.get("id") or entry.get("requestId") or entry.get("uuid")
                    if key not in seen and not inside(parse_time(entry.get("timestamp"))):
                        continue
                    seen.add(key)
                    u = message["usage"]
                    counts = per_message.setdefault(key, {k: 0 for k in USAGE_FIELDS})
                    for field, name in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                                        ("cache_write", "cache_creation_input_tokens"),
                                        ("output", "output_tokens")):
                        counts[field] = max(counts[field], int(u.get(name, 0) or 0))
                    if message.get("model"):
                        models.add(str(message["model"]))
        if not seen:
            return None
        usage = {k: sum(c[k] for c in per_message.values()) for k in USAGE_FIELDS}
        usage["model"] = ",".join(sorted(models)) or "unknown"
        return usage
    if kind == "codex-session":
        before, after, models = None, None, set()
        for path in paths:
            try:
                handle = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    payload = entry.get("payload") or {}
                    if entry.get("type") == "turn_context" and isinstance(payload, dict) and payload.get("model"):
                        models.add(str(payload["model"]))
                    if entry.get("type") != "event_msg" or not isinstance(payload, dict) \
                            or payload.get("type") != "token_count" or not payload.get("info"):
                        continue
                    total = (payload["info"] or {}).get("total_token_usage") or {}
                    stamp = parse_time(entry.get("timestamp"))
                    if start is not None and stamp is not None and stamp < start:
                        before = total
                    elif inside(stamp):
                        after = total
        if after is None:
            return None
        base = before or {}
        diff = lambda k: int(after.get(k, 0) or 0) - int(base.get(k, 0) or 0)
        return {"model": ",".join(sorted(models)) or "unknown",
                "input": diff("input_tokens") - diff("cached_input_tokens"),
                "cache_read": diff("cached_input_tokens"), "cache_write": diff("cache_write_input_tokens"),
                "output": diff("output_tokens")}
    return None


def usage_fields(usage):
    return "\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ()))


def current_session():
    """(kind, id) of the session this command runs in, from the tool's own environment variable."""
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude-session", os.environ["CLAUDE_CODE_SESSION_ID"]
    codex = os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    if codex:
        return "codex-session", codex
    return "in-session", ""


def mark_stage(cwd, tasks, story_id, stage, edge, session_log=None):
    """`--stage-start`/`--stage-end` for a stage run inside a session: the same journal the runner writes."""
    journal = os.path.join(tasks, story_id, ".verify", "journal.tsv")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    kind, session_id = current_session()
    owner = session_owner()
    if owner and claim(cwd, owner) == 3:
        return 3                               # another worker holds the checkout: this stage does not start
    freeze_all(tasks)                          # the earlier stages' logs have caught up by now
    if session_log:
        kind = "claude-session" if "/.claude/" in session_log.replace(os.sep, "/") else "codex-session"
    allowed = session_usage_allowed(cwd)
    with open(journal, "a", encoding="utf-8") as handle:
        if edge == "start":
            # The model the profile asks this tool to run the stage on. A session cannot switch its own
            # model; a subagent may run on it. Which model the window actually used is read from the
            # session log later, and the status shows a request that did not reach the stage.
            profile = read_profile(resolve_profile(None, cwd))
            tool = kind.split("-")[0]
            requested = str(profile.get(f"model.{tool}.{stage}") or profile.get(f"model.{tool}") or "").strip()
            extra = f"\tmodel_requested={requested}" if requested else ""
            handle.write(f"{stamp}\tstage-start\t{stage}\ttool={kind}{extra}\n")
            if requested:
                print(f"model: the profile asks for {requested} — run this stage as a subagent on it where the "
                      f"tool allows; in this session's own context it cannot take effect")
            record_base(cwd, tasks, story_id)
            write_snapshot(cwd, tasks, story_id, f"before-{stage}")
            # A repeat judge round reads the verdict before it — the runner moves it aside the same way.
            verdict = os.path.join(tasks, story_id, "judge.md")
            if stage == "judge" and os.path.isfile(verdict):
                os.replace(verdict, os.path.join(tasks, story_id, ".judge-previous.md"))
                print(f"judge: the previous verdict is {tasks}/{story_id}/.judge-previous.md — account for it")
            print(f"usage: stage {stage} of {story_id} started ({kind})")
            return 0
        started = None
        for line in read_text(journal).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "stage-start" and parts[2] == stage:
                started = parse_time(parts[0])
        # The window is recorded, not summed: a session log lags behind the session — Claude Code writes
        # a response after the tool call it made returns, so the response running this very command is
        # not in the log yet. `--usage` reads the window when the log has caught up.
        # Only the session's id goes into the journal, never a path: the journal is committed with the
        # project, and a path names the machine and the person. The log is found again when it is read.
        source = f"log={session_log}" if session_log else \
            f"session={kind.split('-')[0]}:{session_id}" if session_id and kind != "in-session" else ""
        handle.write(f"{stamp}\tstage-end\t{stage}\texit=0\n")
        write_snapshot(cwd, tasks, story_id, f"after-{stage}")
        record_changes(cwd, tasks, story_id, stage)
        if not allowed:
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\tunknown\n")
            print(f"usage: stage {stage} of {story_id} — unknown (session usage is switched off)")
        elif started and source:
            begun = started.strftime("%Y-%m-%dT%H:%M:%S.") + f"{started.microsecond // 1000:03d}Z"
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\twindow={begun}/{stamp}\t{source}\n")
            print(f"usage: stage {stage} of {story_id} ended — its usage is read from the session log by --usage")
        else:
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\tunknown\n")
            print(f"usage: stage {stage} of {story_id} — unknown (no stage start, or no session log this tool writes)")
    return 0


# --- what a story changed: a record every stage and every mode hands on ------------------------------

# The runner snapshots the working tree before and after every stage (path and sha256 of every file
# git reports as differing from HEAD, untracked ones included, and `deleted` for a tracked file that is
# gone). What a stage changed follows from two snapshots and the list of tracked files,
# deterministically. What the whole story changed follows from two git trees: the one recorded at the
# story's first stage, written without committing anything, and the working tree now — so a project
# without a commit, where `git diff` has nothing to compare against, still gets its diff, and a stage
# run again does not move the story's starting point. Both are written as files the next stage reads
# first, instead of reconstructing them. Paths are relative to the project, which may be a directory
# inside a larger repository.
CHANGE_EXCLUDED = (".agents/factory/",)
DELETED = "deleted"


def tree_snapshot(cwd):
    """{path: sha256 or `deleted`} of every file under `cwd` that git reports as differing from HEAD."""
    listing = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                             cwd=cwd, capture_output=True)
    files = {}
    if listing.returncode != 0:
        return files
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=cwd, capture_output=True,
                            text=True).stdout.strip()
    local = lambda path: path[len(prefix):] if prefix and path.startswith(prefix) else path
    entries = iter(listing.stdout.decode("utf-8", "replace").split("\0"))
    for entry in entries:
        code, path = entry[:2], local(entry[3:])
        if not path:
            continue
        if code[0] in "RC":
            origin = local(next(entries, ""))       # -z writes a rename's source as the next entry
            if code[0] == "R" and origin:
                files[origin] = DELETED
        full = os.path.join(cwd, path)
        if "D" in code:
            files[path] = DELETED
        elif os.path.isfile(full):
            with open(full, "rb") as handle:
                files[path] = hashlib.sha256(handle.read()).hexdigest()
    return files


def write_snapshot(cwd, tasks, story_id, label):
    folder = os.path.join(tasks, story_id, ".verify")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"tree-{label}.txt"), "w", encoding="utf-8") as handle:
        for path, digest in sorted(tree_snapshot(cwd).items()):
            handle.write(f"{digest}  {path}\n")


def load_snapshot(path):
    """{path: digest} from a snapshot file, or None when there is none (or it carries no digests)."""
    if not os.path.isfile(path):
        return None
    files = {}
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            return None
        digest, _, name = line.partition("  ")
        if name:
            files[name] = digest
    return files


def tracked_files(cwd):
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=cwd, capture_output=True)
    return set(listing.stdout.decode("utf-8", "replace").split("\0")) if listing.returncode == 0 else set()


def changes_between(before, after, tasks, tracked=frozenset()):
    """A path missing from a snapshot is as HEAD has it: there when git tracks it, absent otherwise."""
    excluded = CHANGE_EXCLUDED + (tasks.rstrip("/") + "/",)
    state = lambda snapshot, path: snapshot.get(path, "head" if path in tracked else None)
    exists = lambda value: value not in (None, DELETED)
    rows = []
    for path in sorted(set(before) | set(after)):
        if path.startswith(excluded):
            continue
        was, now = state(before, path), state(after, path)
        if was == now or not (exists(was) or exists(now)):
            continue
        rows.append(("removed" if not exists(now) else "added" if not exists(was) else "modified", path))
    return rows


def git_tree(cwd):
    """A tree object of the project as it is — `git add -A` into a throwaway index, never a commit."""
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(scratch, "index"))
        if subprocess.run(["git", "add", "-A", "--", "."], cwd=cwd, env=env, capture_output=True).returncode != 0:
            return None
        tree = subprocess.run(["git", "write-tree"], cwd=cwd, env=env, capture_output=True, text=True)
        return tree.stdout.strip() if tree.returncode == 0 and tree.stdout.strip() else None


def tree_changes(cwd, base, now, tasks):
    """[(kind, path)] between two trees, relative to the project, the run's own files left out."""
    listing = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames", "--relative", base, now, "--", "."],
                             cwd=cwd, capture_output=True)
    if listing.returncode != 0:
        return None
    excluded = CHANGE_EXCLUDED + (tasks.rstrip("/") + "/",)
    fields = listing.stdout.decode("utf-8", "replace").split("\0")
    kinds = {"A": "added", "D": "removed"}
    return [(kinds.get(code[:1], "modified"), path) for code, path in zip(fields[0::2], fields[1::2])
            if path and not path.startswith(excluded)]


def record_base(cwd, tasks, story_id):
    """At a story's first stage: the tree the story's diff is taken against. Written once."""
    folder = os.path.join(tasks, story_id, ".verify")
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "base-tree")
    if not os.path.isfile(base):
        tree = git_tree(cwd)
        with open(base, "w", encoding="utf-8") as handle:
            handle.write((tree or "none") + "\n")


def record_changes(cwd, tasks, story_id, stage):
    """`changed-<stage>.txt`, the story's `changed.txt` and `story.diff`, after a stage has ended."""
    folder = os.path.join(tasks, story_id, ".verify")
    after = load_snapshot(os.path.join(folder, f"tree-after-{stage}.txt"))
    before = load_snapshot(os.path.join(folder, f"tree-before-{stage}.txt"))
    if after is None or before is None:
        return
    tracked = tracked_files(cwd)
    with open(os.path.join(folder, f"changed-{stage}.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in changes_between(before, after, tasks, tracked))
    base_file = os.path.join(folder, "base-tree")
    base = read_text(base_file).strip() if os.path.isfile(base_file) else "none"
    now = git_tree(cwd) if base != "none" else None
    story_rows = tree_changes(cwd, base, now, tasks) if now else None
    if story_rows is None:
        first = next((load_snapshot(os.path.join(folder, f"tree-before-{name}.txt")) for name in STAGE_ORDER
                      if os.path.isfile(os.path.join(folder, f"tree-before-{name}.txt"))), before)
        story_rows = changes_between(first, after, tasks, tracked)
    with open(os.path.join(folder, "changed.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in story_rows)
    diff_path = os.path.join(folder, "story.diff")
    if base == "none" or not now:
        with open(diff_path, "w", encoding="utf-8") as handle:
            handle.write("# no diff: the project is not a git repository, or no base tree was recorded — "
                         "changed.txt lists the files\n")
        return
    paths = [path for _, path in story_rows]
    diff = subprocess.run(["git", "diff", "--no-color", "--relative", base, now, "--"] + paths, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace") if paths else None
    with open(diff_path, "w", encoding="utf-8") as handle:
        handle.write(diff.stdout if diff and diff.returncode == 0 else "")


def listed_files(handover):
    """The paths a hand-over names under `## Files`, or in the build's `## Changed` / tidy's `## Moves`
    table: in backticks, as a list item's first word, or in a table's first column."""
    if not os.path.isfile(handover):
        return None
    names, inside, found = set(), False, False
    for line in read_text(handover).splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() in ("files", "changed", "moves")
            found = found or inside
            continue
        if inside:
            names.update(re.findall(r"`([^`\s]+)`", line))
            item = re.match(r"^\s*[-*]\s+([^\s`|]+)", line)
            if item:
                names.add(item.group(1))
            row = re.match(r"^\|\s*([^|`\s]+)\s*\|", line)
            if row and not set(row.group(1)) <= set("-:"):
                names.add(row.group(1))
    return names if found else None


def check_files_listed(result, tasks, story_id, stage):
    """The test, build and tidy hand-overs name every file the stage changed, so the next stage can read
    those instead of searching. Checked against the changed-files record, never against the claim."""
    record = os.path.join(tasks, story_id, ".verify", f"changed-{stage}.txt")
    if not os.path.isfile(record):
        result.skip("files-listed", f"no changed-files record for {stage} — the stage was not snapshotted")
        return
    changed = [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
    handover = os.path.join(tasks, story_id, STAGE_FILES[stage])
    listed = listed_files(handover)
    if listed is None:
        result.fail("files-listed", f"{STAGE_FILES[stage]} has no `## Files` section (nor a `## Changed` or "
                                    f"`## Moves` table) — list every file the stage changed, one line each")
        return
    missing = [path for path in changed if path not in listed and not any(path.endswith("/" + n) for n in listed)]
    if missing:
        result.fail("files-listed", f"{STAGE_FILES[stage]} does not list what the stage changed: "
                                    f"{', '.join(missing[:8])}" + (" …" if len(missing) > 8 else ""))
        return
    unchanged = sorted(n for n in listed if "/" in n and n not in changed
                       and not any(p.endswith("/" + n) or p == n for p in changed))
    if unchanged:
        result.note("files-listed", f"listed but not changed by this stage: {', '.join(unchanged[:5])}")
    result.ok("files-listed", f"{STAGE_FILES[stage]} lists the {len(changed)} file(s) the stage changed")


#: Seconds after a window's end before its numbers are written into the journal: a session log is
#: written after the tool call that marked the end returns, so a younger window may still grow.
FREEZE_AFTER = 300


def freeze_windows(journal):
    """Write the numbers of every session window that can be read now into the journal itself.

    The window points at a session log on this machine, which a clone does not have and the tool
    deletes after a while. Once read, the journal carries the numbers and no path, so the history
    stays with the project."""
    if not os.path.isfile(journal):
        return
    text = read_text(journal)
    lines, changed = text.splitlines(), False
    settled = datetime.now(timezone.utc).timestamp() - FREEZE_AFTER
    for i, line in enumerate(lines):
        parts = line.split("\t")
        if len(parts) < 4 or parts[1] != "usage" or not any(p.startswith("window=") for p in parts):
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        end = parse_time(fields.get("window", "").partition("/")[2])
        if end is None or end.timestamp() > settled:
            continue                            # the log may still lag behind this window
        read = resolve_window(fields)
        if read is None:
            continue
        lines[i] = "\t".join(parts[:3] + [f"tool={fields.get('tool', '')}", usage_fields(read),
                                            f"window={fields['window']}"])
        changed = True
    if changed:
        # Written aside and moved into place, with whatever was appended while the logs were read —
        # the runner or a stage mark may write a line at any moment.
        grown = read_text(journal)
        tail = grown[len(text):] if grown.startswith(text) else ""
        temporary = f"{journal}.{os.getpid()}"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n" + tail)
        os.replace(temporary, journal)


def freeze_all(tasks):
    """`freeze_windows` over every story's journal. A story's last stages end its run, so no stage
    start of its own ever comes back to freeze them; the next command that writes anyway — a stage
    of another story, a claim, a release, a listening loop's look — does it for them. Never fails
    the command it rides on."""
    for journal in glob.glob(os.path.join(tasks, "*", ".verify", "journal.tsv")):
        with contextlib.suppress(OSError, GateError, ValueError):
            freeze_windows(journal)


def resolve_window(fields):
    """A recorded session window, read now: {usage fields} or None."""
    if not session_usage_allowed(os.getcwd()):
        return None
    kind = fields.get("tool", "")
    start, _, end = fields.get("window", "").partition("/")
    paths = [p for p in fields.get("log", "").split(",") if p]
    tool, _, session_id = fields.get("session", "").partition(":")
    if session_id and tool == "claude":
        paths = claude_session_logs(session_id)
    elif session_id and tool == "codex":
        paths = [p for p in [codex_session_log(session_id)] if p]
    return session_usage(kind, paths, parse_time(start), parse_time(end)) if paths else None


def usage_from(fmt, path, model=None):
    if fmt in ("claude-session", "codex-session"):
        usage = session_usage(fmt, [path])
        print(usage_fields(usage) if usage else "unknown")
        return 0
    usage, text = parse_usage(fmt, path)
    if usage is None:
        print("unknown")
    else:
        if model and not usage.get("model"):
            usage["model"] = model
        usage.setdefault("model", "unknown")
        print("\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ())))
    if text.strip():
        print(text.strip())
    return 0


def journal_usage(tasks, story_id, resolve=True):
    """{stage: {invocations, measured, input, cache_read, cache_write, output, cost}} from the journal.

    `resolve=False` counts only what the journal carries itself, without opening a session log."""
    journal = os.path.join(tasks, story_id, ".verify", "journal.tsv")
    stages = {}
    if not os.path.isfile(journal):
        return stages
    # A journal merged with `merge=union` can hold one session window twice — read on one branch,
    # still pending on the other. A window is one stage run, so it is counted once, the read one first.
    counted_windows = set()
    lines = sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l, l))
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        window = next((p for p in parts if p.startswith("window=")), None)
        if parts[1] == "usage" and window:
            if (parts[2], window) in counted_windows:
                continue
            counted_windows.add((parts[2], window))
        entry = stages.setdefault(parts[2], {"invocations": 0, "measured": 0, "cost": 0.0, "priced": 0,
                                             "seconds": 0, **{k: 0 for k in USAGE_FIELDS}})
        if parts[1] == "usage":
            # wall-clock time of the invocation, recorded by the runner — known even when its tokens
            # are not, and the only cost a local model has
            entry["seconds"] += sum(int(p[8:]) for p in parts[3:] if p.startswith("seconds=") and p[8:].isdigit())
        if parts[1] == "stage-start":
            entry["invocations"] += 1
            for p in parts[3:]:
                if p.startswith("model_requested="):
                    entry.setdefault("requested", set()).add(p.split("=", 1)[1])
                if p.startswith("model_applied=no"):
                    entry["not_applied"] = entry.get("not_applied", 0) + 1
        elif parts[1] == "usage" and "unknown" not in parts[3:]:
            fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            if "window" in fields and ("log" in fields or "session" in fields):
                read = resolve_window(fields) if resolve else None
                if read is None:
                    continue
                fields.update({k: str(v) for k, v in read.items()})
            entry["measured"] += 1
            if fields.get("model") and fields["model"] != "unknown":
                entry.setdefault("models", set()).update(fields["model"].split(","))
            for k in USAGE_FIELDS:
                entry[k] += int(fields.get(k, 0) or 0)
            if fields.get("cost"):
                entry["cost"] += float(fields["cost"])
                entry["priced"] += 1
    return {s: e for s, e in stages.items() if e["invocations"] or e["measured"]}


def stage_rank(stage):
    """Stage order for reports; the shared builder process (plan to tidy in one) sits before the judge."""
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 3.5 if stage == "builder" else 99


def tokens_of(entry):
    return sum(entry[k] for k in USAGE_FIELDS)


def money(entry):
    """The cost where the tool reported one — a session log has none, and that is not free."""
    if not entry["priced"]:
        return "—"
    return f"{entry['cost']:.2f}" + ("" if entry["priced"] == entry["measured"] else "+")


def usage_report(tasks, story_filter=None, total_only=False):
    stories = sorted(d for d in os.listdir(tasks) if os.path.isdir(os.path.join(tasks, d))) \
        if os.path.isdir(tasks) else []
    if story_filter:
        stories = [s for s in stories if s == story_filter]
    if total_only:
        print(sum(tokens_of(e) for s in stories for e in journal_usage(tasks, s).values()))
        return 0
    print(f"{'story/stage':<24} {'runs':>4} {'measured':>8} {'input':>9} {'cache read':>11} "
          f"{'cache write':>11} {'output':>8} {'cost $':>8}")
    grand = None
    for story in stories:
        stages = journal_usage(tasks, story)
        if not stages:
            continue
        order = sorted(stages, key=stage_rank)
        total = {"invocations": 0, "measured": 0, "cost": 0.0, "priced": 0, **{k: 0 for k in USAGE_FIELDS}}
        for stage in order:
            e = stages[stage]
            for k in total:
                total[k] += e[k]
            print(f"{story + '/' + stage:<24} {e['invocations']:>4} {e['measured']:>8} {e['input']:>9} "
                  f"{e['cache_read']:>11} {e['cache_write']:>11} {e['output']:>8} {money(e):>8}")
        print(f"{story + ' total':<24} {total['invocations']:>4} {total['measured']:>8} {total['input']:>9} "
              f"{total['cache_read']:>11} {total['cache_write']:>11} {total['output']:>8} {money(total):>8}")
        unknown = total["invocations"] - total["measured"]
        if unknown > 0:
            print(f"{'':<24} {unknown} invocation(s) without a usage report — not counted, not zero")
        grand = total if grand is None else {k: grand[k] + total[k] for k in grand}
    if grand is None:
        print("usage: no stage invocation recorded")
    elif len([s for s in stories if journal_usage(tasks, s)]) > 1:
        print(f"{'total':<24} {grand['invocations']:>4} {grand['measured']:>8} {grand['input']:>9} "
              f"{grand['cache_read']:>11} {grand['cache_write']:>11} {grand['output']:>8} {money(grand):>8}")
    return 0


# --- one worker per checkout ------------------------------------------------------------

# Two workers on one checkout build on each other's unfinished code. The claim is a file created
# exclusively — of two workers asking at the same moment, one gets it — in the git directory, so it is
# per checkout (a worktree has its own), never committed and never an untracked file the commit check
# would call drift. A holder renews it before every stage; one that stops renewing is stale after
# FACTORY_STALE_AFTER seconds (default two hours) and may be taken over, which is said out loud.
def stale_after():
    try:
        return max(0, int(os.environ.get("FACTORY_STALE_AFTER", "7200")))
    except ValueError:
        return 7200


def claim_path(cwd):
    code, git_dir = git(cwd, "rev-parse", "--git-dir")
    if code == 0 and git_dir:
        return os.path.join(cwd, git_dir, "dca-factory-worker.lock")
    return os.path.join(cwd, ".agents", "factory", "worker.lock")


def session_owner():
    kind, session_id = current_session()
    return f"{kind}:{session_id}" if session_id else ""


def read_claim(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_claim(path, owner, since):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": since or stamp, "beat": stamp}, handle)
    os.replace(temporary, path)


def claim(cwd, owner):
    """0 when `owner` holds the checkout now (claimed, renewed or taken over), 3 when another does."""
    path = claim_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Written aside, then linked into place: a link fails when the claim exists, so the file appears
    # with its content or not at all — an empty claim between create and write would read as unreadable.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}.new"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": stamp, "beat": stamp}, handle)
    try:
        os.link(temporary, path)
        print(f"claim: {owner} holds the checkout")
        return 0
    except FileExistsError:
        pass
    except OSError:                              # a file system without hard links
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(read_text(temporary))
            print(f"claim: {owner} holds the checkout")
            return 0
        except FileExistsError:
            pass
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)
    held = read_claim(path) or {}
    if held.get("owner") == owner:
        write_claim(path, owner, held.get("since"))
        return 0
    beat = parse_time(held.get("beat"))
    if beat is None:                             # unreadable: aged by the file, not taken on sight
        with contextlib.suppress(OSError):
            beat = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    age = (datetime.now(timezone.utc) - beat).total_seconds() if beat else None
    if age is None or age > stale_after():
        write_claim(path, owner, None)
        print(f"claim: took over from {held.get('owner', 'an unreadable claim')} — no sign of life for "
              f"{int(age // 60) if age is not None else '?'} min, so it was stopped or crashed")
        return 0
    print(f"claim: the checkout is held by {held.get('owner')} since {held.get('since')} (last sign of life "
          f"{int(age // 60)} min ago) — one worker per checkout; this one does not start")
    return 3


# A session that listens on the backlog (`/loop /factory-run`) holds no claim while nothing is ready,
# so from outside a waiting listener and an ended one look the same. Each look leaves a mark next to
# the claim — who looked, and when — which `--status` shows. It only informs; it locks nothing.
def listener_path(cwd):
    return claim_path(cwd).replace("dca-factory-worker.lock", "dca-factory-listener.json") \
        if claim_path(cwd).endswith("dca-factory-worker.lock") else \
        os.path.join(cwd, ".agents", "factory", "listener.json")


def listen_stale_after():
    try:
        return max(60, int(os.environ.get("FACTORY_LISTEN_STALE", "3600")))
    except ValueError:
        return 3600


def mark_listening(cwd):
    owner = session_owner() or "a session without an id"
    path = listener_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_claim(path, owner, None)
    print(f"listening: {owner} looked at the backlog")
    return 0


def listener_line(cwd):
    """`listening: …` for the status, or None when no session has looked."""
    held = read_claim(listener_path(cwd))
    if not held:
        return None
    beat = parse_time(held.get("beat"))
    if not beat:
        return None
    minutes = int((datetime.now(timezone.utc) - beat).total_seconds() // 60)
    ended = minutes * 60 > listen_stale_after()
    return (f"listening: {held.get('owner')}, last look {minutes} min ago"
            + (" — no look for longer than a loop waits, probably ended" if ended else ""))


def release(cwd, owner):
    path = claim_path(cwd)
    held = read_claim(path)
    if held and held.get("owner") == owner:
        os.remove(path)
        print(f"claim: {owner} released the checkout")
    return 0


# --- status: one look at the whole pipeline -----------------------------------------

def running_stages(tasks):
    """[(story, stage, started)] for every stage whose journal shows a start and no end yet.

    The journal knows that a stage began, not whether its process is still alive: a stage whose
    runner was killed reads the same, which is why the start time is shown with it."""
    found = []
    if not os.path.isdir(tasks):
        return found
    for story in sorted(os.listdir(tasks)):
        journal = os.path.join(tasks, story, ".verify", "journal.tsv")
        if not os.path.isfile(journal):
            continue
        open_stage = None
        # By time, not by position: a union merge interleaves two branches' lines.
        for line in sorted(read_text(journal).splitlines(), key=lambda l: parse_time(l.split("\t")[0])
                           or datetime.min.replace(tzinfo=timezone.utc)):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            if parts[1] == "stage-start":
                open_stage = (parts[2], parts[0])
            elif parts[1] == "stage-end" and open_stage and parts[2] == open_stage[0]:
                open_stage = None
        if open_stage:
            found.append((story, open_stage[0], open_stage[1]))
    return found


def status_brief(cwd, backlog, tasks, session_start=False):
    """Two lines: what is ready, what waits, who works, what it cost — for a session's start."""
    import contextlib
    import io
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        schedule(cwd, backlog, tasks)
    rows = [l for l in buffer.getvalue().splitlines() if l and not l.startswith(("schedule:", "wait:", "layout:"))]
    nxt = next((l[6:] for l in rows if l.startswith("next: ")), "none")
    states = {}
    for line in rows:
        if line.startswith("next: "):
            continue
        parts = line.split()
        if len(parts) >= 2:
            states.setdefault(parts[1], []).append(parts[0])
    open_ids = [name for name, _f, _b, state, _e in decision_files(cwd) if state in ("open", "draft")]
    held = read_claim(claim_path(cwd))
    stories = sorted(d for d in os.listdir(tasks) if os.path.isdir(os.path.join(tasks, d))) \
        if os.path.isdir(tasks) else []
    tokens = sum(tokens_of(e) for s in stories for e in journal_usage(tasks, s, resolve=False).values())
    summary = " · ".join(f"{len(v)} {k}" for k, v in sorted(states.items())) or "no stories yet"
    print(f"factory: {summary}" + (f" · {tokens:,} tokens so far" if tokens else ""))
    print("factory: " + (f"{len(open_ids)} question(s) wait for you: {', '.join(open_ids)} · " if open_ids else "")
          + (f"worker {held.get('owner')} holds the checkout · " if held else "no worker running · ")
          + f"next: {nxt}")
    listening = listener_line(cwd)
    if listening:
        print(f"factory: {listening}")
    # The part of the factory that is missing, where the files show it: the description, the backlog.
    profile = read_profile(resolve_profile(None, cwd))
    undescribed = [key for key in ("product", "tech") if not os.path.isfile(os.path.join(cwd, location(profile, key)))]
    if layout_hint(cwd, profile):
        print(f"factory: {layout_hint(cwd, profile)}")
    elif undescribed:
        print(f"factory: no project description ({', '.join(location(profile, k) for k in undescribed)}) — /factory-setup")
    elif not states:
        print("factory: the backlog is empty — /factory-backlog writes the first epic and story")
    if session_start:
        print("dca-factory: this project delivers stories through the factory. At the person's first message, "
              "unless they already name a task, show the two lines above and ask what they want to do: write or "
              "release a story (/factory-backlog), answer a waiting question (/factory-decisions), start working "
              "the backlog (/factory-run, which keeps asking the schedule; in Claude Code also /loop /factory-run), "
              "or look closer (/factory-status). A session never runs `factory.sh run` — it starts a tool "
              "process per stage. A managing session writes backlog and decision files only; the worker is the "
              "one writer in the checkout.")
    return 0


def duplicate_pipeline_note(cwd):
    """A session sees the person's plugins as well as the project's skills. With the dca-factory plugin
    enabled and a project copy installed, a stage run in the session may pick either copy — the
    runner's stage processes see only the project, a session does not."""
    if not os.path.isfile(os.path.join(cwd, ".claude", "skills", "factory-run", "SKILL.md")):
        return None
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    for settings in (os.path.join(home, "settings.json"), os.path.join(cwd, ".claude", "settings.json"),
                     os.path.join(cwd, ".claude", "settings.local.json")):
        try:
            with open(settings, encoding="utf-8") as handle:
                enabled = (json.load(handle) or {}).get("enabledPlugins") or {}
        except (OSError, ValueError):
            continue
        if any(str(key).startswith("dca-factory@") and value for key, value in enabled.items()):
            return ("note: the dca-factory plugin is enabled and the project has its own copy — a stage run in a "
                    "session may pick the plugin's skills; the runner's stages see only the project's")
    return None


def activity_logs(cwd, owner, since):
    """The session logs a running stage writes into while it works: the worker's own session and its
    subagents where the claim names a session, else the tool's logs for this project directory that
    changed since the stage started (a runner's stage process has a session of its own)."""
    kind, _, session_id = (owner or "").partition(":")
    if kind == "claude-session":
        return claude_session_logs(session_id)
    if kind == "codex-session":
        found = codex_session_log(session_id)
        return [found] if found else []
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    folder = os.path.join(home, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd)))
    floor = since.timestamp() if since else 0
    return [path for path in glob.glob(os.path.join(folder, "**", "*.jsonl"), recursive=True)
            if os.path.getmtime(path) >= floor]


def last_tool_call(path):
    """`Name: first words of its input` of the newest tool call in a Claude or Codex session log."""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - 262144))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
        for block in reversed(content if isinstance(content, list) else []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                given = block.get("input") or {}
                detail = next((str(given[k]) for k in ("command", "description", "skill", "file_path", "pattern")
                               if isinstance(given, dict) and given.get(k)), "")
                detail = " ".join(detail.split())
                return f"{block.get('name')}" + (f": {detail[:70]}" + ("…" if len(detail) > 70 else "") if detail else "")
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if payload.get("type") in ("function_call", "local_shell_call"):
            return str(payload.get("name") or payload.get("type"))
    return ""


def activity_line(cwd, owner, started, now):
    """The sign of life inside a stage: a stage writes to the journal only at its start and its end,
    while its session log grows with every tool call. Read only where session logs may be read."""
    if not session_usage_allowed(cwd):
        return "activity: not read — session logs are switched off (sessionUsage)"
    logs = [path for path in activity_logs(cwd, owner, parse_time(started)) if os.path.isfile(path)]
    if not logs:
        return "activity: unknown — no session log of this stage found on this machine"
    newest = max(logs, key=os.path.getmtime)
    age = int(now.timestamp() - os.path.getmtime(newest))
    ago = f"{age} s ago" if age < 120 else f"{age // 60} min ago"
    call = last_tool_call(newest)
    return f"activity: {ago}" + (f" — last tool call {call}" if call else "")


def status(cwd, backlog, tasks, story_filter=None):
    now = datetime.now(timezone.utc)
    print("== running")
    running = running_stages(tasks)
    for story, stage, started in running:
        since = parse_time(started)
        minutes = int((now - since).total_seconds() // 60) if since else None
        print(f"{story}  stage {stage}  since {started}" + (f"  ({minutes} min)" if minutes is not None else ""))
    if not running:
        print("nothing — no stage has a start without an end in any journal")
    held = read_claim(claim_path(cwd))
    for story, stage, started in running:
        print(activity_line(cwd, (held or {}).get("owner", ""), started, now))
    if held:
        beat = parse_time(held.get("beat"))
        age = int((now - beat).total_seconds() // 60) if beat else None
        print(f"worker: {held.get('owner')} since {held.get('since')}, last claim "
              + (f"{age} min ago" if age is not None else "unknown")
              + (" — stale, the next worker takes over" if age is not None and age * 60 > stale_after() else ""))
    else:
        print("worker: none holds the checkout")
    listening = listener_line(cwd)
    print(listening or "listening: no session has looked at the backlog")
    duplicate = duplicate_pipeline_note(cwd)
    if duplicate:
        print(duplicate)
    print("\n== waiting for a human")
    waiting = 0
    for name, front, body, state, error in decision_files(cwd):
        if error:
            print(f"{name}  unreadable — {error}")
            waiting += 1
        elif state in ("open", "draft"):
            waiting += 1
            question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
            print(f"{front.get('id', name)}  {state}  {front.get('story', '?')}/{front.get('stage', '?')}  "
                  f"{question}")
    if not waiting:
        print("nothing — no open decision record")
    print("\n== stories")
    schedule(cwd, backlog, tasks)
    print("\n== cost" + (f" of {story_filter}, per stage" if story_filter else ""))
    if story_filter:
        return cost_by_stage(tasks, story_filter)
    return cost_by_story(tasks)


def model_cell(entry):
    """The model(s) a stage actually ran on, and a request that did not reach it, said as such."""
    models = sorted(entry.get("models", ()))
    requested = sorted(r for r in entry.get("requested", ()) if r and r != "default")
    cell = ",".join(models) if models else ("—" if "models" in entry or "requested" in entry else "")
    missing = [r for r in requested if not any(r in m for m in models)]
    if entry.get("not_applied"):
        cell += f"  (requested {','.join(requested) or '?'}: not applied)"
    elif missing and models:
        cell += f"  (requested {','.join(missing)}: not what ran)"
    return cell


def duration(seconds):
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds else "—"


def cost_by_story(tasks):
    """One row per story and the total — what the backlog cost so far."""
    stories = sorted(d for d in os.listdir(tasks) if os.path.isdir(os.path.join(tasks, d))) if os.path.isdir(tasks) else []
    rows, total = [], {"invocations": 0, "measured": 0, "cost": 0.0, "priced": 0, **{k: 0 for k in USAGE_FIELDS}}
    for story in stories:
        stages = journal_usage(tasks, story).values()
        if not stages:
            continue
        entry = {k: sum(e[k] for e in stages) for k in total}
        rows.append((story, entry))
        for k in total:
            total[k] += entry[k]
    if not rows:
        print("nothing — no stage invocation recorded in any journal")
        return 0
    print(f"{'story':<24} {'runs':>4} {'measured':>8} {'tokens':>12} {'cost $':>8}")
    for name, e in rows + [("total", total)]:
        print(f"{name:<24} {e['invocations']:>4} {e['measured']:>8} {tokens_of(e):>12,} {money(e):>8}")
    unknown = total["invocations"] - total["measured"]
    if unknown > 0:
        print(f"{unknown} invocation(s) without a usage report — not counted, not zero")
    print("per stage: status <story>")
    return 0


def cost_by_stage(tasks, story):
    """One row per stage of one story and its total."""
    stages = journal_usage(tasks, story)
    if not stages:
        print(f"nothing — no stage invocation recorded for {story}")
        return 0
    order = sorted(stages, key=stage_rank)
    numeric = [k for k, v in stages[order[0]].items() if isinstance(v, (int, float))]
    total = {k: sum(stages[s].get(k, 0) for s in order) for k in numeric}
    timed = total.get("seconds", 0) > 0
    print(f"{'stage':<24} {'runs':>4} {'measured':>8} {'input':>9} {'cache read':>11} "
          f"{'cache write':>11} {'output':>8} {'tokens':>12} {'cost $':>8}" + (f" {'time':>8}" if timed else "")
          + "  model")
    # (rows are right-stripped, so a stage without a model reading ends at its cost)
    for name, e in [(s, stages[s]) for s in order] + [("total", total)]:
        print(f"{name:<24} {e['invocations']:>4} {e['measured']:>8} {e['input']:>9} {e['cache_read']:>11} "
              f"{e['cache_write']:>11} {e['output']:>8} {tokens_of(e):>12,} {money(e):>8}"
              + ((f" {duration(e.get('seconds', 0)):>8}" if timed else "") + "  " + model_cell(e)).rstrip())
    unknown = total["invocations"] - total["measured"]
    if unknown > 0:
        print(f"{unknown} invocation(s) without a usage report — not counted, not zero")
    return 0


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


#: What a gate leaves for the schedule. The plan gate records the story it let through, so a story
#: edited afterwards is planned again rather than built on a plan that describes something else; the
#: document gate records that it passed, so "delivered" is a gate's verdict and not a file's existence.
STORY_DIGEST, DELIVERED = ".story-digest", ".delivered"


def file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write_mark(tasks, story_id, name, content):
    folder = os.path.join(tasks, story_id)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        handle.write(content + "\n")


def story_state(cwd, tasks, story_id, front, story_path=None):
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
    answered, resolved = {}, {}
    for _path, front_, _body, state, _answer in records:
        rid, asked_by = str(front_["id"]).strip(), str(front_.get("stage", "")).strip()
        text = texts.get(asked_by)
        if state in ("answered", "applied"):
            resolved[rid] = asked_by
        # The record's `stage:` applies the answer — usually the stage that asked, for a judge's
        # story conflict the stage the answer lands in. Until that stage's file cites the id, it is next.
        if state == "answered" and (text is None or rid in (needs_human_ids(text) or []) or rid not in text):
            answered.setdefault(asked_by, rid)
    if answered:
        stage = min(answered, key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 0)
        return "resumable", stage, f"decision {answered[stage]} answered — its stage applies it"
    rounds_file = os.path.join(folder, ".rounds")
    if os.path.isfile(rounds_file) and (read_text(rounds_file).strip() or "0").isdigit() \
            and int(read_text(rounds_file).strip() or "0") >= MAX_ROUNDS:
        return "stopped", None, f"{MAX_ROUNDS} rounds did not converge"
    refusal = os.path.join(folder, ".gate-plan.txt")
    if os.path.isfile(refusal):
        # Repaired since: the story or its epic is newer than the refusal, so the plan gate asks again.
        sources = [p for p in (story_path, story_path and os.path.join(os.path.dirname(story_path), "epic.md"))
                   if p and os.path.isfile(p)]
        if not any(os.path.getmtime(p) > os.path.getmtime(refusal) for p in sources):
            return "stopped", None, "the plan gate refused the story — the backlog needs a fix"
        return "in-progress", "plan", "the story changed after the plan gate refused it — planned again"
    conflict = needs_human_ids(texts.get("judge", "")) or []
    if verdict_in(texts.get("judge", "")) == "story-conflict" and conflict and all(i in resolved for i in conflict):
        applied_at = max((resolved[i] for i in conflict),
                         key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 0)
        after = STAGE_ORDER[min(STAGE_ORDER.index(applied_at) + 1, len(STAGE_ORDER) - 1)] \
            if applied_at in STAGE_ORDER else "build"
        return "in-progress", after, (f"the story conflict was answered and applied at {applied_at} — "
                                      f"the stages after it run again")
    for stage, text in texts.items():
        ids = needs_human_ids(text)
        if ids and all(i in resolved for i in ids):
            continue
        if ids is not None:
            return "stopped", None, f"{STAGE_FILES[stage]} ends in `## needs-human` without an open record"
    if verdict_in(texts.get("judge", "")) == "story-conflict":
        return "stopped", None, "the judge found a story conflict"
    planned = os.path.join(folder, STORY_DIGEST)
    if story_path and texts and os.path.isfile(planned) and os.path.isfile(os.path.join(folder, "plan.md")) \
            and not os.path.isfile(os.path.join(folder, DELIVERED)) \
            and read_text(planned).strip() != file_digest(story_path):
        return "in-progress", "plan", "the story changed after it was planned — every stage runs again"
    refused = [stage for stage in STAGE_ORDER
               if os.path.isfile(os.path.join(folder, f".gate-{stage}.txt"))]
    if refused:
        return "in-progress", refused[0], f"the {refused[0]} gate refused — the stage runs again"
    if "document" in texts:
        if os.path.isfile(os.path.join(folder, DELIVERED)):
            return "delivered", None, ""
        return "in-progress", "document", "document.md is written, its gate has not passed yet"
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
    hint = layout_hint(cwd, read_profile(resolve_profile(None, cwd)))
    if hint:
        print(f"layout: {hint}")
    for root, _dirs, files in os.walk(backlog):
        # A story is `backlog/<epic>/<story>.md`; a file beside the epics — a README — is not one.
        if os.path.normpath(root) == os.path.normpath(backlog):
            continue
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
            state, start, detail = story_state(cwd, tasks, story_id, front, path)
            stories[story_id] = dict(state=state, start=start, detail=detail, deps=depends_on(front),
                                     holds=state not in ("delivered", "superseded") and os.path.isfile(
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

    # A stage that started and has not ended is running — unless it has shown no sign of life for longer
    # than a stage may take, then it was interrupted and the story may be picked up again.
    now = datetime.now(timezone.utc)
    for story_id, stage, started in running_stages(tasks):
        if story_id not in stories:
            continue
        since = parse_time(started)
        if since and (now - since).total_seconds() <= stale_after():
            stories[story_id].update(state="running", start=None, detail=f"stage {stage} since {started}")
        else:
            stories[story_id]["detail"] = (stories[story_id]["detail"] + " · " if stories[story_id]["detail"] else "") \
                + f"stage {stage} started {started} and never ended — possibly interrupted"
    holders = [s for s in order if stories[s].get("holds")]
    nxt, reason, wait = None, "", False
    if holders:
        holder = stories[holders[0]]
        if holder["state"] in RUNNABLE:
            nxt = holders[0]
        else:
            reason = (f"{holders[0]} holds unfinished code in the checkout ({holder['state']}) — "
                      f"no other story starts until it is delivered")
            wait = holder["state"] in ("waiting", "running")
    else:
        busy = [s for s in order if stories[s]["state"] == "running"]
        nxt = None if busy else next((s for s in order if stories[s]["state"] in RUNNABLE), None)
        wait = any(stories[s]["state"] in ("waiting", "running") for s in order)
        if busy:
            reason = f"{busy[0]} is running ({stories[busy[0]]['detail']}) — one story at a time per checkout"
        elif nxt is None:
            reason = "nothing can run"

    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        # What the story cost so far, from the runner's journal — kept per story on disk, so a
        # restart, a second session or a new run never resets it. An in-session run writes none.
        journal = os.path.join(tasks, story_id, ".verify", "journal.tsv")
        spent = ""
        if os.path.isfile(journal):
            used = journal_usage(tasks, story_id)
            count = sum(e["invocations"] for e in used.values())
            tokens = sum(tokens_of(e) for e in used.values())
            spent = (f" · {count} stage invocation(s)" + (f", {tokens:,} tokens" if tokens else "")) if count else ""
        print(f"{story_id}  {story['state']:<11} {start:<13} {story['detail']}{spent}".rstrip())
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
    parser.add_argument("--claim", metavar="OWNER", help="take the checkout for one worker (exit 3: held by another)")
    parser.add_argument("--release", nargs="?", const="", metavar="OWNER",
                        help="give the checkout back (default: this session's claim)")
    parser.add_argument("--check-contract", action="store_true",
                        help="check the profile's contract and model keys alone (the runner, before its first stage)")
    parser.add_argument("--record-base", action="store_true",
                        help="with --story: record the tree the story's diff is taken against (the first stage)")
    parser.add_argument("--record-changes", metavar="STAGE",
                        help="with --story: write changed-<stage>.txt, changed.txt and story.diff from the snapshots")
    parser.add_argument("--project", action="store_true",
                        help="check the project description — product and technical — alone, and exit")
    parser.add_argument("--listening", action="store_true",
                        help="record that this session looked at the backlog (a listening loop's sign of life)")
    parser.add_argument("--status", action="store_true",
                        help="print what runs, what waits for a human, every story's state and the cost")
    parser.add_argument("--brief", action="store_true", help="with --status: two lines, for a session's start")
    parser.add_argument("--session-start", action="store_true",
                        help="with --status --brief: add what a session should do with them (the SessionStart hook)")
    parser.add_argument("--usage", action="store_true",
                        help="print the tokens each story and stage used, from the runner's journals")
    parser.add_argument("--total", action="store_true", help="with --usage: print only the token total")
    parser.add_argument("--usage-from", nargs=2, metavar=("FORMAT", "FILE"),
                        help="read one invocation's usage from a tool's raw output (claude-json, codex-jsonl, opencode-json)")
    parser.add_argument("--usage-model", help="with --usage-from: the model, where the output does not name it")
    parser.add_argument("--stage-start", metavar="STAGE", help="mark a stage's start inside a session (with --story)")
    parser.add_argument("--stage-end", metavar="STAGE",
                        help="mark its end and record what it used, read from the session's own log")
    parser.add_argument("--session-log", help="with --stage-end: the session log to read, where it is not found")
    parser.add_argument("--schedule", action="store_true",
                        help="print every story's state and the next one to run, and exit")
    parser.add_argument("--check-backlog", action="store_true",
                        help="the plan gate's backlog checks over every story that is not done (or --story), "
                             "writing nothing, and exit")
    parser.add_argument("--backlog", help="backlog root (default: the profile's `backlog:`, else project/backlog)")
    parser.add_argument("--tasks", default="tasks")
    parser.add_argument("--profile")
    parser.add_argument("--root", default=".", help="the project's root directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.root)
    os.chdir(cwd)
    # Where the backlog is: the flag, else the profile, else `project/backlog`. No default depends on
    # the contract, and none reads the layout before `project/` — the gate names the move instead.
    if not args.backlog:
        args.backlog = location(read_profile(resolve_profile(args.profile, cwd)), "backlog")
    if args.list_decisions:
        return list_decisions(cwd, args.story)
    if args.schedule:
        return schedule(cwd, args.backlog, args.tasks)
    if args.check_backlog:
        return check_backlog(cwd, args.backlog, args.tasks, read_profile(resolve_profile(args.profile, cwd)),
                             args.story)
    if args.check_contract:
        result = Result()
        profile = read_profile(resolve_profile(args.profile, cwd))
        check_contract(result, profile)
        check_models(result, profile)
        for state, check, message in result.entries:
            if state != "pass":
                print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else 0
    if args.record_base or args.record_changes:
        if not args.story:
            parser.error("--record-base/--record-changes need --story")
        if args.record_base:
            record_base(cwd, args.tasks, args.story)
        if args.record_changes:
            record_changes(cwd, args.tasks, args.story, args.record_changes)
        return 0
    if args.project:
        result = Result()
        try:
            profile = read_profile(resolve_profile(args.profile, cwd))
            check_project(result, cwd, profile)
            if layout_hint(cwd, profile):
                result.note("layout", layout_hint(cwd, profile))
        except GateError as error:
            result.fail("project", str(error))
        for state, check, message in result.entries:
            print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else (3 if any(e[0] == "note" for e in result.entries) else 0)
    if args.listening or args.claim or args.release is not None:
        freeze_all(args.tasks)
    if args.listening:
        return mark_listening(cwd)
    if args.claim:
        return claim(cwd, args.claim)
    if args.release is not None:
        return release(cwd, args.release or session_owner())
    if args.status and args.brief:
        try:
            return status_brief(cwd, args.backlog, args.tasks, args.session_start)
        except Exception as error:                      # a hook must never break a session's start
            print(f"factory: status unavailable ({error.__class__.__name__})")
            return 0
    if args.status:
        return status(cwd, args.backlog, args.tasks, args.story)
    if args.stage_start or args.stage_end:
        if not args.story:
            parser.error("--stage-start/--stage-end need --story")
        return mark_stage(cwd, args.tasks, args.story, args.stage_start or args.stage_end,
                          "start" if args.stage_start else "end", args.session_log)
    if args.usage_from:
        return usage_from(args.usage_from[0], args.usage_from[1], args.usage_model)
    if args.usage:
        return usage_report(args.tasks, args.story, args.total)
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
    hint = layout_hint(cwd, read_profile(resolve_profile(args.profile, cwd)))
    if hint:
        result.note("layout", hint)
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
            check_project(result, cwd, profile)
            check_models(result, profile)
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
            check_files_listed(result, args.tasks, story_id, args.stage)
            check_existing_tests(result, cwd, args.tasks, story_id, body)
            check_stage_commands(result, profile, cwd, args.stage)
    except GateError as error:
        result.fail("gate", str(error))
        return result.report(args.story, args.stage, args.json)
    if not result.failed and args.stage == "plan":
        write_mark(args.tasks, story_id, STORY_DIGEST, file_digest(story_path))
        record_tests_baseline(cwd, args.tasks, story_id)
    if not result.failed and args.stage == "document":
        write_mark(args.tasks, story_id, DELIVERED, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return result.report(story_id, args.stage, args.json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
