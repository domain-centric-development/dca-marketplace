"""Story gate — the deterministic part of a factory run: what decides.

Reads the backlog (markdown with front matter) and the stack profile, then checks what a stage may
not decide for itself. Exit code 0 means the stage may proceed. What only *shows* the pipeline —
status, help, usage, session logs, the checkout claim, the schedule — is `factory-cli.py` beside this
file; a flag that moved there is handed over, so an older caller still gets its answer.

    story-gate.py --story <id> --stage <plan|test|build|tidy|document|adopt> [options]
    story-gate.py --change [--staged] [--checks <c>]   the profile's checks outside a story; --staged
                                                       checks what the commit contains (the hook, CI)
    story-gate.py --parity <config>                    every implementation's reports prove every
                                                       mandatory scenario of a scenario contract
    story-gate.py --check-backlog [--story <id>]       the plan gate's backlog checks over every story
                                                       that is not done; exit 1 when one is refused
    story-gate.py --project                            the project description (product and technical)
                                                       alone; exit 3 while a part is missing, 1 when
                                                       one is incomplete
    story-gate.py --check-contract                     the profile's contract and model keys alone
    story-gate.py --record-base | --record-changes <stage>   the tree a story's diff is taken against,
                                                       and what a stage changed (with --story)

Options:
    --epics <dir>       where the epics and stories are (default: the profile's `epics:`, else project/epics)
    --runs <dir>        the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)
    --root <dir>        the project's root (default: .)
    --profile <file>    stack profile (default: dca-factory.profile.yaml in the project root)
    --json              additionally print the result as one JSON object

Checks by stage:
    plan   epic completeness (intent, goal, metric, domain_contact), story well-formed and not
           left in draft, its bounded context present in the context map, the round limit not
           reached, and a note when the project instructions are too large for a tool to load
    test   epic + every acceptance criterion mapped to a test in <runs>/<story>/tests.md,
           the test exists in the sources, the test sources compile, every mapped test is red.
           Which selectors were red is recorded in <evidence>/<story>/.tests-red
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
    every stage  the story's decision records in its folder (`<story>/decisions/`): a `## needs-human`
           section names one, an open one stops the story, an answered one is applied by the
           stage that asked and then stamped `## Applied` here

Where things are — one owner per place: `project/` is the people's (the description, the epics with
their stories, each story a folder with its decisions), `.agents/factory/` is the installed pipeline,
the profile at the root is the person's, and `.dca-factory/` is the run's protocol (hand-overs, marks,
the journal), disposable at any time: what is delivered stands in the story itself (`status:
delivered`, written by the gate alone), so deleting the run folder loses history, never state.

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import calendar
import contextlib
import glob
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import typing
from datetime import datetime, timezone
from .contract import (
    runs_top,
    ANSWER_FIELDS, answered_decisions, CONTEXT_MAP_CANDIDATES, CONTRACT, CRITERION, decisions_store, delivered_on,
    DOC_BUDGET_BYTES, duplicate_ids, epic_dependency_problem, EPIC_FIELDS, EPIC_FILE, epic_folder, evidence_dir,
    factory_home, file_digest, find_story, findings_path, GateError, git, HAPPY_MARK, HOME_VARIABLE, in_worktree,
    INSTRUCTION_FILES, is_delivered, JOURNEY_ORDER, layout_hint, location, MAPPING_ROW, MAX_ROUNDS, needs_human_ids,
    NOTHING, place, PROFILE_FILE, read_decisions, read_front_matter, read_profile, read_text, record_findings,
    record_path, records_of, resolve_profile, resume_stage, section_of, SELECTOR, set_places, SHARED_WINDOWS, shown,
    STAGE, STAGE_CHECKS, STAGE_FILES, STAGE_ORDER, STAGES, stamp_applied, story_digest, story_files, story_folder,
    story_id_of, story_kind, TECH_HEADINGS, VERSION)
from .reports import (
    clock_marker, display_name_of, executed_tests, fill, normalise, outcome_for, read_scenarios, report_state,
    reported_names, reports_from_this_run, SENTINEL, unescape_literal)
from .state import (
    ACCEPTANCE_KIND, acceptance_mode, acceptance_records, acceptance_state, accepted, backlog_digest,
    current_stage_files, git_tree, is_acceptance, journal_append, last_ended, listed_files, MODEL_PROCESSES,
    NOT_OBSERVED, observe_writes, OWNED_CHANGED, owned_changes, owned_end, PRODUCT_HEADINGS, record_base,
    record_changes, record_owned, run_owned, snapshot_reason, stage_open, STORY_DIGEST, tree_changes, verdict_in,
    window_open, write_mark, write_story_fields)


def check_owned(result, runs, story_id, story_path):
    """Inside a window, and after one that changed what is the person's, the gate refuses."""
    marked = os.path.join(evidence_dir(runs, story_id), OWNED_CHANGED)
    if os.path.isfile(marked):
        parts = [line.split(":", 1)[1].strip() for line in read_text(marked).splitlines() if line.startswith("changed:")]
        result.fail("owned", f"{', '.join(parts)} changed under a stage — a person looks at it and confirms "
                             f"(`factory-cli.py --owned-confirm {story_id}`) before the story runs on")
        return
    changed = owned_changes(runs, story_id, story_path)
    if changed:
        result.fail("owned", f"{', '.join(changed)} changed while this stage runs — the story and the answers are the "
                             f"person's; a stage writes its question into a record, never an answer, and never the story")
    elif changed is not None:
        result.ok("owned", "the story and the answers are as the stage found them")


def story_ids(epics):
    """Every story id under the epics, in the order of the files — front matter first, else the file name."""
    return [story_id_of(path) for path in story_files(epics)]


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
            key = re.sub(r"\s*\(happy path\)$", "", line[5:].strip())
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


def happy_paths(body):
    """The keys marked `(happy path)` under the acceptance criteria."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    return [m.group(1) for m in (HAPPY_MARK.match(l.strip()) for l in section.splitlines()) if m]


def contract_of(profile):
    declared = str(profile.get("contract", "")).strip()
    return int(declared) if declared.isdigit() else CONTRACT


def check_happy_path(result, story_path, front, body, profile):
    """Contract 9: exactly one happy path per story, marked in the backlog — never picked by a plan. A
    journey has none: it is a guard, not acceptance, and it names the stories it depends on."""
    if story_kind(front) == "journey":
        needs = front.get("depends_on")
        if isinstance(needs, str):
            needs = [n.strip() for n in needs.strip("[] ").split(",") if n.strip()]
        if not needs:
            result.fail("journey", f"{story_path}: a `kind: journey` item names the stories whose steps it walks "
                                   f"under `depends_on:` — it becomes ready when they are delivered")
        else:
            result.ok("journey", f"journey over {', '.join(needs) if isinstance(needs, list) else needs}")
        return
    if story_kind(front) == "adopt":
        result.skip("happy-path", "an adopted story tests nothing new — the levels are the existing tests'")
        return
    if contract_of(profile) < 9:
        result.skip("happy-path", f"the profile declares contract {contract_of(profile)} — the happy-path mark "
                                  f"is contract 9's")
        return
    marked = happy_paths(body)
    if len(marked) == 1:
        result.ok("happy-path", f"happy path: {marked[0]}")
    else:
        result.fail("happy-path", f"{story_path}: {len(marked)} scenarios marked `(happy path)` — exactly one per "
                                  f"story shows its value and gets the end-to-end test; mark it in the backlog "
                                  f"(`#### <key> (happy path)`)" + (f": {', '.join(marked)}" if marked else ""))


TITLE_LINE = re.compile(r"^Title:\s*(\S.*?)\s*$")


def scenario_titles(body):
    """{key: title} for every criterion: the `Title:` line under a scenario's heading, else the key in words
    (`shows-empty-state` → "Shows empty state"). An end-user test carries it verbatim as its display name, so two
    implementations of one story name the test alike and a report names the scenario it proves."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    titles, current = {}, None
    for line in section.splitlines():
        stripped = line.strip()
        heading = re.match(r"^####\s+([a-z0-9][a-z0-9-]*)", stripped)
        criterion = CRITERION.match(stripped)
        if heading:
            current = heading.group(1)
            titles[current] = current.replace("-", " ").capitalize()
        elif criterion:
            current = None
            titles[criterion.group(1)] = criterion.group(1).replace("-", " ").capitalize()
        elif current and TITLE_LINE.match(stripped) and "{{" not in stripped:   # a template placeholder names nothing
            titles[current] = TITLE_LINE.match(stripped).group(1)
    return titles


def carries_title(path, method, title):
    """The test is reported under the title: its display name where the declaration gives one, else a string
    literal that is the title — never the words somewhere in a comment or another test."""
    display = display_name_of(path, method)
    if display is not None:
        return display == title
    text = read_text(path) if os.path.isfile(path) else ""
    return any(unescape_literal(m.group(2)) == title
               for m in re.finditer(r"""(["'`])((?:\\.|(?!\1).)*)\1""", text))


def check_titles(result, profile, cwd, front, body, mapping, located):
    """Contract 9: an end-user test carries its scenario's title verbatim, as its display name."""
    if story_kind(front) == "adopt" or contract_of(profile) < 9 or not mapping or not profile.get("e2eTest"):
        return
    titles = scenario_titles(body)
    wrong = []
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            path = located.get(selector)
            if not path or command_for(profile, path)[0] not in ("e2eTest", "test.journey") or key not in titles:
                continue
            if not carries_title(os.path.join(cwd, path), selector.split("#", 1)[-1], titles[key]):
                wrong.append(f"{selector} ({key}) — \"{titles[key]}\"")
    if wrong:
        result.fail("test-titles", "end-user tests without their scenario's title as display name — write it "
                                   "verbatim (the scenario's `Title:` line, else its key in words): " + "; ".join(wrong))
    elif any(command_for(profile, located.get(sel) or "")[0] == "e2eTest"
             for sels in mapping.values() for sel in sels if located.get(sel)):
        result.ok("test-titles", "every end-user test carries its scenario's title")


def plan_levels(runs, story_id):
    """The keys the plan gave `browser-only` — a `Then` only a browser can observe, with its reason."""
    text = read_text(os.path.join(runs, story_id, "plan.md")) if os.path.isfile(os.path.join(runs, story_id, "plan.md")) else ""
    return {m.group(1) for m in re.finditer(r"^\s*-\s+([a-z0-9][a-z0-9-]*)\b[^\n]*level:\s*browser-only", text, re.M)}


def check_plan_levels(result, runs, story_id):
    """A plan line the pipeline's skeleton wrote and the stage never finished — a key with no level after it —
    is a plan that was not made: refused at the test gate, before any test is read against it."""
    path = os.path.join(runs, story_id, "plan.md")
    if not os.path.isfile(path):
        return
    unfinished = [m.group(1) for m in re.finditer(r"^\s*-\s+([a-z0-9][a-z0-9-]*)\s+→\s+level:\s*$", read_text(path), re.M)]
    if unfinished:
        result.fail("plan-levels", f"plan.md gives no level to {', '.join(unfinished[:6])}"
                                   + (" …" if len(unfinished) > 6 else "")
                                   + " — the skeleton's line is still empty; the plan stage gives each criterion "
                                     "`level: e2e | integration | browser-only (<why>)`")


#: The kinds of a plan's `## Changes` row that carry invariants: the domain's own types. A use case, a port, an
#: adapter or a read model has none of its own — its rules are the domain's, reached through the use case.
DOMAIN_KINDS = re.compile(r"\b(aggregate|entity|value object|value|domain service)\b", re.I)


def first_identifier(cell):
    """The name a table cell or a list item starts with — `Task`, `` `TaskCompleted(eventId, …)` ``, `Task — field
    state` all start with their element's name; what follows it is description, never part of the name."""
    match = re.search(r"[A-Za-z_][\w.]*", cell)
    return match.group(0) if match else ""


def plan_domain_elements(plan):
    """The elements of the plan's `## Changes` table whose kind is a domain type, in the table's order."""
    elements = []
    for line in section_of(plan, "changes") or []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].strip("` ").lower() == "element":
            continue
        name = first_identifier(cells[0])
        if name and DOMAIN_KINDS.search(cells[1]) and not re.search(r"\bevent\b", cells[1], re.I):
            elements.append(name)
    return elements


def split_rules(text):
    """A plan invariant line's rules, split at `;` outside parentheses and backticks — `complete() (open → done;
    done → no change)` is one rule."""
    rules, depth, tick, current = [], 0, False, ""
    for char in text:
        if char == "`":
            tick = not tick
        elif not tick and char in "([":
            depth += 1
        elif not tick and char in ")]" and depth:
            depth -= 1
        if char == ";" and depth == 0 and not tick:
            rules.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        rules.append(current.strip())
    return [r for r in rules if r]


def plan_invariants(plan):
    """`## Invariants` as {element: [rule, …]}: one line per domain type, `- <Element>: <rule>; <rule>`, or
    `- <Element>: none — <why>` (an empty list). None when the section is absent."""
    lines = section_of(plan, "invariants")
    if lines is None:
        return None
    found = {}
    for line in lines:
        match = re.match(r"^\s*-\s+(.+?)\s*:\s*(.+?)\s*$", line)
        if not match:
            continue
        name = first_identifier(match.group(1))
        # The part before the `:` is one element's name — bare, in backticks, or followed by a dash and a
        # description. A sentence there (`- The aggregate Task: …`, `- Note on the rules: …`) names no element.
        if not name or not re.fullmatch(rf"[`*]*{re.escape(name)}[`*]*(\s*\([^)]*\))?(\s+[—–-].*)?",
                                        match.group(1).strip()):
            continue
        rules = match.group(2)
        found[name] = [] if re.match(r"^none\b", rules, re.I) else split_rules(rules)
    return found


INVARIANTS_MARKER = "<!-- gate:invariants -->"


def read_invariant_rows(text):
    """The `gate:invariants` table of tests.md: [(element, [rule numbers], selector)] — `| TaskTitle | 1 | <rule> |
    <Class>#<method> |`, several numbers as `1, 2`; the selector is the last cell. None when the table is absent."""
    if INVARIANTS_MARKER not in text:
        return None
    rows = []
    for line in text.split(INVARIANTS_MARKER, 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")] if stripped.startswith("|") else []
        if len(cells) < 3 or cells[0].lower() == "element" or set(cells[0]) <= set("-: "):
            continue
        numbers = [int(n) for n in re.findall(r"\d+", cells[1])]
        rows.append((first_identifier(cells[0]), numbers, cells[-1]))
    return rows


def locate_selector(cwd, selector):
    """The file that holds `<Class>#<method>`: a file named after the class, in its package, that mentions the method."""
    match = SELECTOR.match(selector)
    if not match:
        return None
    cls, method = match.groups()
    simple = cls.rsplit(".", 1)[-1]
    candidates = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in BREAK_IGNORE and not d.startswith(".")]
        candidates += [os.path.join(root, f) for f in files if os.path.splitext(f)[0] == simple]
    found = [path for path in in_package(candidates, cls) if contains(path, method)]
    return found[0] if found else None


def check_invariants(result, profile, cwd, runs, story_id, front, mapping):
    """Contract 13: every domain type the plan changes names its invariants — its rules, the guards included, one
    per `;` — and every rule has its own unit test in tests.md's `gate:invariants` table: a selector that exists as
    class and method, and that is no criterion's test. A guard nobody named is code no test asked for; a rule whose
    only test is a criterion's is a rule nobody tested on its own."""
    if story_kind(front) != "story" or contract_of(profile) < 13:
        return
    plan_path, tests_path = os.path.join(runs, story_id, "plan.md"), os.path.join(runs, story_id, "tests.md")
    if not os.path.isfile(plan_path):
        return
    plan = read_text(plan_path)
    elements, named = plan_domain_elements(plan), plan_invariants(plan) or {}
    if not elements and not any(named.values()):
        return
    missing = [e for e in elements if e not in named]
    if missing:
        result.fail("invariants", "plan.md changes domain types without an `## Invariants` line: "
                                  + ", ".join(missing) + " — name each one's rules, its guards included "
                                  "(`- <Element>: <rule>; <rule>`), or `- <Element>: none — <why>`")
        return
    if not any(named.values()):
        result.ok("invariants", "every domain type the plan changes names why it has no invariant of its own")
        return
    rows = read_invariant_rows(read_text(tests_path)) if os.path.isfile(tests_path) else None
    if rows is None:
        result.fail("invariants", f"tests.md has no `{INVARIANTS_MARKER}` table under `## Invariants` — "
                                  "`factory-cli.py --files-skeleton <story> test` writes it with one row per rule; "
                                  "fill in each row's test")
        return
    criterion_tests = {sel for sels in mapping.values() for sel in sels}
    covered, problems = set(), []
    for element, numbers, selector in rows:
        rules = named.get(element)
        if rules is None:
            problems.append(f"{element} is not in plan.md's `## Invariants`")
            continue
        wrong = [n for n in numbers if not 1 <= n <= len(rules)]
        if not numbers or wrong:
            problems.append(f"{element} has {len(rules)} rule(s), the row names {', '.join(map(str, wrong)) or 'none'}")
            continue
        if not selector:
            continue                          # the skeleton's row, not filled: reported as untested below
        if not SELECTOR.match(selector):
            problems.append(f"{selector!r} is not `<Class>#<method>`")
        elif selector in criterion_tests:
            problems.append(f"{selector} is a criterion's test — an invariant gets a unit test of its own")
        elif not locate_selector(cwd, selector):
            problems.append(f"{selector} is not in the project (no file named after the class mentions the method)")
        else:
            covered.update((element, n) for n in numbers)
    untested = [f"{e} {n} ({rules[n - 1][:60]})" for e, rules in named.items() for n in range(1, len(rules) + 1)
                if (e, n) not in covered]
    if problems:
        result.fail("invariants", "the `gate:invariants` table: " + "; ".join(problems[:6]) + (" …" if len(problems) > 6 else ""))
    elif untested:
        result.fail("invariants", "invariants without a unit test of their own: " + "; ".join(untested[:6])
                                  + (" …" if len(untested) > 6 else "") + " — the row's last cell, `<Class>#<method>`")
    else:
        result.ok("invariants", f"every rule the plan names has a unit test of its own "
                                f"({sum(len(r) for r in named.values())} rules, {len(rows)} rows)")


CLAUSES_MARKER = "<!-- gate:clauses -->"


CLAUSE_LEVELS = ("unit", "port", "adapter", "e2e")


#: Words that make a clause a statement about what is stored — it holds through the input port with the real store,
#: never in an adapter test whose input ports are stubs, where the assertion only reads back the stub's answer.
STATE_WORDS = re.compile(r"\b(bleibt|bleiben|unverändert|weiterhin|danach|gespeichert|gelöscht|remains?|stays?|"
                         r"unchanged|still|afterwards|stored|persisted|deleted)\b", re.IGNORECASE)


def scenario_clauses(body):
    """{scenario key: [(n, "Then …" / "And …")]} — what each scenario says is observed: its `Then` and every `And` or
    `But` after it, numbered from 1. The `Given` and `When` steps are the arrangement, not an expectation."""
    clauses, key, phase, collecting = {}, None, None, False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue
        if line.startswith("#### "):
            key, phase = re.sub(r"\s*\(happy path\)$", "", line[5:].strip()), None
            continue
        step = STEP.match(stripped)
        if not step or key is None:
            continue
        word, text = step.groups()
        if word in ("Given", "When", "Then"):
            phase = word
        if phase == "Then" and word in ("Then", "And", "But"):
            entries = clauses.setdefault(key, [])
            entries.append((len(entries) + 1, f"{word} {text}".strip()))
    return clauses


def read_clause_rows(text):
    """The `gate:clauses` table of tests.md: [(key, n, location, level)] — `| <key> | <n> | <clause> | <File>:<line> |
    <level> |`. None when the table is absent."""
    if CLAUSES_MARKER not in text:
        return None
    rows = []
    for line in text.split(CLAUSES_MARKER, 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")] if stripped.startswith("|") else []
        if len(cells) < 5 or cells[0].lower() == "criterion" or set(cells[0]) <= set("-: "):
            continue
        number = re.match(r"\d+", cells[1])
        rows.append((cells[0], int(number.group()) if number else 0, cells[3], cells[4].lower()))
    return rows


def asserts_at(path, number):
    """Whether the statement at line `number` of `path` asserts: the line or the three before it (a call chain's
    start) carry an assertion library's call, a framework's expectation or a mock's verification."""
    try:
        lines = read_text(path).splitlines()
    except OSError:
        return False
    if not 1 <= number <= len(lines):
        return False
    return bool(ASSERTION_STATEMENT.search(" ".join(lines[max(number - 4, 0):number])))


def check_clauses(result, profile, cwd, runs, story_id, front, body, mapping, located):
    """Contract 15: every expectation of every scenario — its `Then` and each `And` after it — names the line of the
    test that asserts it, in tests.md's `gate:clauses` table, with the level it runs at. A clause without a line is
    an expectation nobody asserted; a clause about what is stored, asserted in an adapter test against stubbed input
    ports, asserts only the stub. Both reached the judge as majors, run after run."""
    if story_kind(front) != "story" or contract_of(profile) < 15:
        return
    wanted = scenario_clauses(body)
    if not wanted:
        return
    tests_path = os.path.join(runs, story_id, "tests.md")
    rows = read_clause_rows(read_text(tests_path)) if os.path.isfile(tests_path) else None
    if rows is None:
        result.fail("clauses", f"tests.md has no `{CLAUSES_MARKER}` table under `## Clauses` — `factory-cli.py "
                               "--files-skeleton <story> test` writes one row per `Then`/`And`; fill in each row's "
                               "`<File>:<line>` and level")
        return
    given = {(key, n): (location, level) for key, n, location, level in rows}
    problems, state_on_stub, counted = [], [], 0
    for key, clauses in wanted.items():
        own = {os.path.normpath(located[s]) for s in mapping.get(key, []) if located.get(s)}
        for n, clause in clauses:
            location, level = given.get((key, n), ("", ""))
            if not location:
                problems.append(f"{key} {n} ({clause[:50]}) has no assertion line")
                continue
            found = re.match(r"(.+?):L?(\d+)", location)
            path = os.path.join(cwd, found.group(1)) if found else ""
            if not found or not os.path.isfile(path):
                problems.append(f"{key} {n}: `{location}` is no `<File>:<line>` in the project")
                continue
            if not asserts_at(path, int(found.group(2))):
                problems.append(f"{key} {n}: `{location}` asserts nothing — no assertion at or just above that line")
                continue
            if own and os.path.normpath(path) not in own and not re.search(r"(^|/)tests?[^/]*/", found.group(1)):
                problems.append(f"{key} {n}: `{location}` is in no test of {key} and no test source")
                continue
            if level not in CLAUSE_LEVELS:
                problems.append(f"{key} {n}: level `{level or '—'}` is none of {', '.join(CLAUSE_LEVELS)}")
                continue
            if level == "adapter" and STATE_WORDS.search(clause):
                state_on_stub.append(f"{key} {n} ({clause[:60]})")
                continue
            counted += 1
    if problems:
        result.fail("clauses", "the `gate:clauses` table: " + "; ".join(problems[:6]) + (" …" if len(problems) > 6 else ""))
    elif state_on_stub:
        result.fail("clauses", "clauses about what is stored, asserted at the adapter level: " + "; ".join(state_on_stub[:6])
                               + " — an adapter test's input ports are stubs, so the assertion reads back the stub; "
                               "assert the clause through the input port with the real store (`port`), or end to end")
    else:
        result.ok("clauses", f"every expectation of every scenario names its assertion ({counted} clause(s))")


def check_levels(result, profile, runs, story_id, front, body, mapping, located):
    """Contract 9: a scenario's test runs at the lowest level that observes its `Then`. A test the
    end-user command runs belongs to the happy path or to a scenario the plan gave `browser-only`;
    every other end-user test is a browser test where an integrated one would do."""
    if story_kind(front) != "story" or contract_of(profile) < 9 or not mapping or not profile.get("e2eTest"):
        return
    allowed = set(happy_paths(body)) | plan_levels(runs, story_id)
    wrong = []
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            path = located.get(selector)
            if path and command_for(profile, path)[0] == "e2eTest" and key not in allowed:
                wrong.append(f"{key} ({selector})")
    if wrong:
        result.fail("levels", "end-user tests for scenarios that are neither the happy path nor `browser-only` in "
                              "the plan — integrate them (a `test.<name>:` source set), or give the plan's line "
                              "`level: browser-only (<why>)`: " + "; ".join(wrong))
    else:
        result.ok("levels", "every end-user test belongs to the happy path or a browser-only scenario")


BREAK_IGNORE = (".git", "build", "bin", "obj", "target", "node_modules", ".gradle", "TestResults", "out")


def copy_for_break(cwd, copy):
    """The project as a scratch copy for a break: in git the files git sees — tracked, and new ones it does not
    ignore — so a package that happens to be called `build` comes along; outside git, everything but
    the build outputs and the run folder at the project's top level."""
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=cwd,
                            capture_output=True)
    if listed.returncode != 0:
        top = os.path.abspath(cwd)
        ignored = BREAK_IGNORE + (runs_top(),)
        shutil.copytree(cwd, copy, symlinks=True,
                        ignore=lambda folder, names: [n for n in names if n in ignored
                                                      and (os.path.abspath(folder) == top or n in (".git", "node_modules"))])
        return
    for name in sorted({n for n in listed.stdout.decode("utf-8", "replace").split("\0") if n}):
        source, target = os.path.join(cwd, name), os.path.join(copy, name)
        if not os.path.lexists(source):
            continue                          # deleted in the tree, still in the index
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        elif os.path.isfile(source):
            shutil.copy2(source, target)


def break_path(runs, story_id, selector):
    return os.path.join(runs, story_id, "breaks", selector.replace("#", "--").replace("/", "_") + ".patch")


def characterization_tests(runs, story_id):
    """The selectors under `## Characterization` in tests.md — the tests the adoption wrote itself."""
    text = read_text(os.path.join(runs, story_id, "tests.md")) if os.path.isfile(os.path.join(runs, story_id, "tests.md")) else ""
    section = text.split("## Characterization", 1)[1].split("\n## ", 1)[0] if "## Characterization" in text else ""
    return [m.group(1) for m in re.finditer(r"^\s*-\s+`?([\w.$]+#[\w$]+)`?", section, re.M)]


def check_adopt(result, profile, cwd, runs, story_id, front, criteria):
    """The adopt gate: an adopted story is delivered when every scenario maps to a test that exists and
    is green, a fresh judge passed it, and every test the adoption wrote itself turns red under its
    break — a minimal change to the production code, applied to a scratch copy, never to the tree."""
    if story_kind(front) != "adopt":
        result.fail("adopt", "the adopt gate is for a story with `status: adopted`")
        return
    mapping = check_mapping(result, runs, story_id, criteria)
    located = check_exists(result, cwd, mapping)
    check_compiles(result, profile, cwd)
    check_test_state(result, profile, cwd, mapping, "green", located, runs, story_id, guard=True)
    judge = read_text(os.path.join(runs, story_id, "judge.md")) if os.path.isfile(os.path.join(runs, story_id, "judge.md")) else ""
    if verdict_in(judge) != "pass":
        result.fail("adopt-judged", f"judge.md carries no `verdict: pass` — a fresh judge confirms that each "
                                    f"mapped test asserts its scenario before the story counts as adopted")
    else:
        result.ok("adopt-judged", "the judge confirmed that the tests prove the scenarios")
    everything = str(profile.get("adopt.breakProof", "")).strip().lower() == "all"
    by_selector = {sel: key for key, sels in mapping.items() for sel in sels}
    written = [qualify_selector(sel, by_selector, cwd) for sel in characterization_tests(runs, story_id)]
    wanted = sorted(by_selector) if everything else written
    extra = {sel for sel in wanted if sel not in located}
    if extra:
        located = dict(located, **check_exists(Result(), cwd, {"outside the table": sorted(extra)}))
    for selector in wanted:
        check_break(result, profile, cwd, runs, story_id, selector, by_selector.get(selector, "outside the table"),
                    located)
    if not wanted:
        result.skip("break-proof", "the adoption wrote no test of its own — every scenario maps to an existing "
                                   "test, which the judge read")


def qualify_selector(selector, by_selector, cwd):
    """A test named by its simple class (`WidgetTest#shows`) as the table names it, or with the package its file
    declares: the report the gate reads names the class in full."""
    cls, _, method = selector.partition("#")
    if "." in cls:
        return selector
    for known in by_selector:
        known_cls, _, known_method = known.partition("#")
        if known_method == method and known_cls.rsplit(".", 1)[-1] == cls:
            return known
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in BREAK_IGNORE]
        for name in files:
            if os.path.splitext(name)[0] == cls:
                package = re.search(r"^\s*(?:package|namespace)\s+([\w.]+)", read_text(os.path.join(root, name)), re.M)
                if package:
                    return f"{package.group(1)}.{cls}#{method}"
    return selector


def check_break(result, profile, cwd, runs, story_id, selector, key, located):
    patch = break_path(runs, story_id, selector)
    if not os.path.isfile(patch):
        short = selector.split("#")[0].rsplit(".", 1)[-1] + "#" + selector.split("#", 1)[-1]
        patch = break_path(runs, story_id, short) if os.path.isfile(break_path(runs, story_id, short)) else patch
    if not os.path.isfile(patch):
        result.fail("break-proof", f"{selector} ({key}): no break at {os.path.relpath(patch, cwd)} — a test that is "
                                   f"green without ever being seen red (one an adoption wrote, one strengthened after "
                                   f"its build) is shown to work by one change to the code that turns it red")
        return
    scratch = tempfile.mkdtemp(prefix="dca-break-")
    try:
        copy = os.path.join(scratch, "tree")
        copy_for_break(cwd, copy)
        applied = subprocess.run(["git", "apply", "--whitespace=nowarn", os.path.abspath(patch)], cwd=copy,
                                 capture_output=True, text=True)
        with open(patch, "rb") as handle:
            raw = handle.read()
        if applied.returncode != 0 and b"\r\n" in raw:
            # An editor on Windows writes the patch with CRLF, which git reads as part of each line.
            unix = os.path.join(scratch, "break.patch")
            with open(unix, "wb") as handle:
                handle.write(re.sub(rb"\r+\n", b"\n", raw))
            applied = subprocess.run(["git", "apply", "--whitespace=nowarn", unix], cwd=copy,
                                     capture_output=True, text=True)
        if applied.returncode != 0:
            result.fail("break-proof", f"{selector} ({key}): its break does not apply — "
                                       f"{(applied.stderr or applied.stdout).strip()[:200]}")
            return
        probe = Result()
        check_test_state(probe, profile, copy, {key: [selector]}, "red", {selector: located.get(selector)} if located.get(selector) else {})
        seen = [(st, m) for st, c, m in probe.entries if c == "tests-red"]
        if seen and all(st == "pass" for st, _m in seen):
            result.ok("break-proof", f"{selector} ({key}): red under its break, on a scratch copy")
        elif any(st == "fail" and ("passes" in m or "is green" in m or "green before" in m) for st, m in seen):
            result.fail("break-proof", f"{selector} ({key}): stays green under its break — the test does not "
                                       f"notice the behaviour it claims to prove")
        else:
            said = "; ".join(m for _st, m in seen)[:300] or "no run of it was recorded"
            result.fail("break-proof", f"{selector} ({key}): its break could not be checked — {said}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def epic_of(story_path, front, epics):
    named = front.get("epic")
    if isinstance(named, list) or not named:
        raise GateError(f"{story_path}: front matter has no `epic:`")
    for candidate in (
        os.path.join(epic_folder(story_path), EPIC_FILE),
        os.path.join(epics, str(named), EPIC_FILE),
    ):
        if os.path.isfile(candidate):
            return candidate, str(named)
    raise GateError(
        f"{story_path}: epic {named!r} has no epic.md — create "
        f"{os.path.join(epics, str(named), 'epic.md')}"
    )


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
    elif status == "adopted":
        result.ok("approved", "story is adopted — it describes behaviour the project already has; adopted, never built")
    elif status == "delivered":
        result.ok("approved", f"story is delivered ({delivered_on(front) or 'no date'}) — checked, nothing runs")
    else:
        result.fail(
            "approved",
            f"{story_path}: status is {status!r} — a human releases the story "
            f"(`status: approved`) before code is written. The most expensive mistake is "
            f"well-built wrong code.",
        )


def check_rounds(result, runs, story_id):
    """The repeat counter lives in a file, so an in-session run cannot lose count and a
    resumed run sees the same number."""
    path = os.path.join(evidence_dir(runs, story_id), ".rounds")
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


def normal_name(name):
    name = name.strip().strip("`*_\"' ").lower()
    return re.sub(r"\s+(bounded\s+)?context$", "", name).strip()


def map_names(text):
    """The names a context map gives: whole table cells, headings, bold names, list items and the nodes of a
    Mermaid diagram. A context is on the map when it is one of them — not when its name is part of another's
    (`order` inside `order-fulfilment`) or of a sentence."""
    names, in_diagram = set(), False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_diagram = stripped.lower().startswith("```mermaid") and not in_diagram
            continue
        if in_diagram:
            names |= {normal_name(t) for t in re.findall(r"[\w-]+", stripped)}
            names |= {normal_name(t) for t in re.findall(r"[\[(\"]([^\])\"]+)[\])\"]", stripped)}
            continue
        if stripped.startswith("|"):
            names |= {normal_name(cell) for cell in stripped.strip("|").split("|")}
        elif stripped.startswith("#"):
            names.add(normal_name(stripped.lstrip("#")))
        elif re.match(r"[-*+]\s", stripped):
            names.add(normal_name(re.split(r"\s[—–:-]\s|:", stripped[2:], maxsplit=1)[0]))
        names |= {normal_name(m) for m in re.findall(r"\*\*([^*]+)\*\*", stripped)}
    return names - {""}


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
    if normal_name(context) in map_names(read_text(os.path.join(cwd, path))):
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
        elif len(parts) == 3 and parts[2] not in STAGE_ORDER + MODEL_PROCESSES:
            bad.append(f"`{key}`: no stage `{parts[2]}` ({', '.join(STAGE_ORDER + MODEL_PROCESSES)})")
        elif len(parts) > 3:
            bad.append(f"`{key}` is not `model.<tool>.<stage>`")
        elif not str(profile[key]).strip():
            bad.append(f"`{key}` has no value")
    if bad:
        result.fail("models", "; ".join(bad))
    else:
        result.ok("models", f"{len(keys)} model key(s), each bound to a tool")


def description_part(cwd, profile, key, headings):
    """One part of the project description as it stands: where it is, whether it is there, which required
    headings are missing or empty, and every `## ` heading it carries. Guidance in HTML comments does not count
    as content, so an untouched template is empty."""
    path = location(profile, key)
    full = os.path.join(cwd, path)
    part = dict(part=key, path=path.replace(os.sep, "/"), present=os.path.isfile(full), missing=[], empty=[],
                sections=[], required=list(headings))
    if not part["present"]:
        return part
    text = re.sub(r"<!--.*?-->", "", read_text(full), flags=re.S)
    sections, order, current = {}, [], None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
            order.append(line[3:].strip())
        elif current is not None:
            sections[current].append(line)
    part["sections"] = order
    part["missing"] = [h for h in headings if h.lower() not in sections]
    part["empty"] = [h for h in headings if h.lower() in sections and not "".join(sections[h.lower()]).strip()]
    return part


def check_described(result, cwd, profile, key, headings, what):
    """One part of the project description. Absent is a note — the gate does not block a project
    that has none, the backlog skill does. A key that names a missing file is a broken reference,
    and a heading missing or empty is a description nobody finished: both fail."""
    named = str(profile.get(key, "")).strip()
    part = description_part(cwd, profile, key, headings)
    path, missing, empty = part["path"], part["missing"], part["empty"]
    if not part["present"]:
        if named:
            result.fail(key, f"the profile's `{key}: {named}` names no file")
        else:
            result.note(key, f"no {what} at {path} — `/factory-setup` writes it before the first story")
        return False
    if missing or empty:
        detail = "; ".join(filter(None, [
            f"missing `## {'`, `## '.join(missing)}`" if missing else "",
            f"empty `## {'`, `## '.join(empty)}`" if empty else "",
        ]))
        result.fail(key, f"{path}: {detail} — every heading gets one honest line, never a placeholder")
        return False
    result.ok(key, f"{path} fills all {len(headings)} headings of the {what}")
    return True


#: Where the method keeps the project's conventions; `verify_command:` there is the architecture command the
#: profile's `architecture:` was copied from at setup. Two files, two owners — the method's and the factory's —
#: and nothing merges them, so the pair is compared and a difference is named.
CONVENTIONS_FILES = (".agents/dca/conventions.md", ".claude/dca/conventions.md")


def conventions_drift(cwd, profile):
    """One line when the profile's `architecture:` and the conventions' `verify_command:` differ; None when
    they agree or one side has nothing to compare. Named, never fixed: the person decides which is right."""
    path = find_first(cwd, CONVENTIONS_FILES)
    declared = str(profile.get("architecture", "")).strip()
    if not path or not declared:
        return None
    stated = ""
    for line in read_text(os.path.join(cwd, path)).splitlines():
        if line.split(":", 1)[0].strip() == "verify_command":
            stated = line.split(":", 1)[1].strip().strip("`")
            break
    if not stated or stated == declared:
        return None
    return (f"architecture: the profile runs `{declared}`, {path} says `verify_command: {stated}` — the gate "
            f"and the method's review would run different commands; make one of the two right")


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


def proposal_words(term):
    """The words the gate looks for in a glossary for one proposed term: the term as written, the domain
    word before a parenthesis and the code word inside it — `Titel (title)` is found by `titel` or by
    `title`. Case does not count."""
    term = term.strip().strip("`*").lower()
    words = {term}
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", term)
    if match:
        words |= {match.group(1).strip(), match.group(2).strip()}
    return {w for w in words if w}


def plan_proposals(plan):
    """The terms a plan proposes under `## Glossary proposals`: the part before the colon of each list item."""
    proposals, collecting = [], False
    for line in plan.splitlines():
        if line.strip().lower().startswith("## glossary proposals"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting and line.strip().startswith("-") and ":" in line:
            proposals.append(line.strip()[1:].split(":", 1)[0].strip().strip("`*"))
    return proposals


def check_proposals_landed(result, runs, story_id, cwd, profile):
    """Every term the plan proposed is either in a glossary now or named as still open. A proposal that
    quietly disappears is how a model's private vocabulary enters a code base. A term is found in a
    glossary by any of its words (`proposal_words`), and it is named open only under `## Not documented`
    of document.md — a row the pipeline pre-filled under `## Glossary` names it, it does not account for it."""
    plan_path = os.path.join(runs, story_id, "plan.md")
    try:
        plan = read_text(plan_path)
    except GateError:
        return
    proposals = plan_proposals(plan)
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
    open_section = ""
    try:
        document = read_text(os.path.join(runs, story_id, "document.md"))
        collecting = False
        for line in document.splitlines():
            if line.startswith("## "):
                collecting = line[3:].strip().lower() == "not documented"
                continue
            if collecting:
                open_section += line.lower() + "\n"
    except GateError:
        pass
    missing = [
        term
        for term in proposals
        if not any(word in corpus for word in proposal_words(term))
        and not any(word in open_section for word in proposal_words(term))
    ]
    if missing:
        result.fail(
            "glossary",
            f"proposed but neither in a glossary nor named as open under `## Not documented`: {', '.join(missing)} — "
            f"a term the code uses and no glossary defines is private vocabulary (a term is found by the word before "
            f"the parenthesis or the word inside it, case aside)",
        )
    else:
        result.ok("glossary", f"{len(proposals)} proposed term(s) accounted for")


def check_backlog(cwd, epics, profile, only=None):
    """The plan gate's backlog checks over every story that is not done, or over `only`: front
    matter, the epic's completeness, the criteria, the status and the context on the map. Nothing of
    its own — the same functions the plan gate calls, so a story that passes here passes there on
    these points. A draft is a story still being written, named and not refused. It writes nothing:
    the plan gate's marks (the story digest, the tests baseline) belong to the run that plans the
    story, and a baseline taken while the story is still being written would be the wrong one."""
    checked, refused = 0, []
    if layout_hint(cwd, profile):
        print(f"gate:note layout — {layout_hint(cwd, profile)}")
    twice = duplicate_ids(epics)
    for sid, paths in sorted(twice.items()):
        print(f"gate:fail {sid} story — id {sid!r} is not unique: {' and '.join(shown(p) for p in paths)}; "
              f"an id names one story in the whole project, give one of them another")
        refused.append(sid)
    for path in story_files(epics):
        name = os.path.basename(story_folder(path))
        result, label = Result(), name
        try:
            front, body = read_front_matter(path)
            label = str(front.get("id") or label).strip()
            if only and only not in (label, name):
                continue
            if label.lower() in twice:
                continue                            # refused above, once for both
            status = str(front.get("status", "")).strip().lower()
            if status == "superseded" or is_delivered(front):
                continue
            if status == "draft":
                result.note("approved", f"{path}: a draft — released with `status: approved` once it is written")
            elif status and status not in ("approved", "adopted"):
                result.fail("approved", f"{path}: status {status!r} is none of draft, approved, adopted, superseded")
            context = str(front.get("context", "")).strip()
            if not context:
                result.fail("story", f"{path}: front matter has no `context:` — a story names the bounded "
                                     f"context it changes")
            criteria = criteria_of(path, body)
            if context:
                result.ok("story", f"{label} in context {context} with {len(criteria)} criterion(s)")
                check_context_map(result, cwd, profile, context)
            check_epic(result, path, front, epics)
            check_outcome_named(result, profile, path, front, epics)
            check_happy_path(result, path, front, body, profile)
        except GateError as error:
            result.fail("story", str(error))
        checked += 1
        for state, check, message in result.entries:
            if state != "pass":
                print(f"gate:{state} {label} {check} — {message}")
        if result.failed:
            refused.append(label)
    if not checked and not refused:
        if only:
            print(f"backlog: no story {only} to check under {epics}/ (not there, delivered or superseded)")
            return 1
        print(f"backlog: no story to check under {epics}/")
        return 0
    print(f"backlog: {checked} story(ies) checked" + (f", refused: {', '.join(refused)}" if refused
                                                     else " — every one holds for the plan gate"))
    return 1 if refused else 0


def check_epic(result, story_path, front, epics):
    epic_path, epic_name = epic_of(story_path, front, epics)
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
    elif str(epic_front.get("discovery") or "").strip() and \
            not os.path.isfile(str(epic_front["discovery"]).strip().strip("`")):
        result.fail("epic", f"{epic_path}: `discovery: {str(epic_front['discovery']).strip()}` names a report that is "
                            f"not there — the epic links the discovery it came from, or no `discovery:` line")
    else:
        result.ok("epic", f"epic {epic_name!r} complete ({', '.join(EPIC_FIELDS)})")
    problem = epic_dependency_problem(epics, epic_name)
    if problem:
        result.fail("epic", f"{epic_path}: {problem}")


#: A source file of the project's code: the gate reads no profile key for where the code lives, so it reads every
#: file with a code extension outside the build's and the tools' folders and outside the tests.
CODE_FILE = re.compile(r"\.(java|kt|scala|groovy|cs|fs|py|ts|tsx|js|jsx|mjs|go|rb|php|rs|swift)$")


#: A test folder by name — `test`, `tests`, `test-utils`, `Foo.Tests`, and the camel-cased source set a build tool
#: names (`integrationTest`, `functionalTests`): a capital T after a lowercase letter, so `latest` and `contest` are not.
TEST_DIR = re.compile(r"(?i:^(tests?|specs?|__tests__)$|^tests?[-_.]|[-_.]tests?$)|[a-z]Tests?$")


#: A line that names a type without using it: an import, a using, a package or namespace line.
IMPORT_LINE = re.compile(r"^\s*(?:import|using|package|namespace|from\s+\S+\s+import)\b.*$", re.M)


def publishes_of(front):
    """The outcome events a story's `publishes:` names — one, or a list."""
    value = front.get("publishes")
    items = value if isinstance(value, list) else split_list(value)
    return [str(item).strip().strip("`") for item in items if str(item).strip().strip("`")]


def production_files(cwd):
    found = []
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith(".") and not TEST_DIR.search(d))
        for name in sorted(files):
            if CODE_FILE.search(name) and not TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


def check_outcome_named(result, profile, story_path, front, epics):
    """Contract 14 (WP-84 V1): the event a story declares under `publishes:` is the epic's outcome event — a word of
    its `metric:`. Two names for one outcome are found here, before a line of code is written."""
    if story_kind(front) != "story" or contract_of(profile) < 14:
        return
    events = publishes_of(front)
    if not events:
        return
    epic_path, epic_name = epic_of(story_path, front, epics)
    metric = str(read_front_matter(epic_path)[0].get("metric", ""))
    foreign = [e for e in events if not re.search(rf"(?<!\w){re.escape(e)}(?!\w)", metric)]
    if foreign:
        result.fail("outcome", f"the story publishes {', '.join(foreign)}, which epic {epic_name!r}'s `metric:` does not "
                               f"name ({metric.strip() or 'empty'}) — the story names the epic's outcome event as the "
                               f"epic does, or the epic's metric is corrected first")
    else:
        result.ok("outcome", f"the story publishes {', '.join(events)}, the outcome event epic {epic_name!r} is measured by")


def check_outcome_raised(result, profile, cwd, runs, story_id, front):
    """Contract 14 (WP-84 V1): delivered means the outcome event exists. Every event of `publishes:` is a type the
    production code declares, and a production file the story changed — the aggregate that raises it or the use case
    that publishes it — refers to it beyond the declaration: another file, or the declaring file itself where the
    event is nested in the aggregate that raises it."""
    if story_kind(front) != "story" or contract_of(profile) < 14:
        return
    events = publishes_of(front)
    if not events:
        return
    files = production_files(cwd)
    texts = {rel: read_text(os.path.join(cwd, rel)) for rel in files}
    record = os.path.join(evidence_dir(runs, story_id), "changed.txt")
    changed, scope = None, "the story changed"
    if os.path.isfile(record) and not read_text(record).startswith(NOT_OBSERVED):
        changed = {parts[1] for parts in (line.split("\t", 1) for line in read_text(record).splitlines())
                   if len(parts) == 2 and parts[0] in ("added", "modified")}
    if changed is None:
        scope = "the project has (no record of what the story changed)"
    problems, found = [], []
    for event in events:
        declares = re.compile(rf"\b(?:class|record|interface|struct|enum|object|type)\s+{re.escape(event)}\b")
        declared = [rel for rel, text in texts.items() if declares.search(text)]
        if not declared:
            problems.append(f"no type `{event}` in the production code — the story says it publishes it")
            continue
        mention = re.compile(rf"(?<!\w){re.escape(event)}(?!\w)")

        constructs = re.compile(rf"\bnew\s+{re.escape(event)}\b|(?<!\w){re.escape(event)}\s*\.\s*\w+\s*\(")

        def raises(rel, text):
            # The event's own file (`TaskCompleted.java`) never raises it: its factory names it, nothing else does.
            # An import, using or package line names it without raising it. A declaring file raises it where the
            # event is nested in it (the aggregate) and constructed there — `new TaskCompleted(…)`, `TaskCompleted.of(…)`.
            if os.path.splitext(os.path.basename(rel))[0] == event.rsplit(".", 1)[-1]:
                return False
            body = IMPORT_LINE.sub("", text)
            return bool(constructs.search(body)) if rel in declared else bool(mention.search(body))
        raising = [rel for rel, text in texts.items() if raises(rel, text)]
        raisers = [rel for rel in raising if changed is None or rel in changed]
        if not raisers and raising:
            problems.append(f"`{event}` is declared in {declared[0]} and raised in {raising[0]}, but by nothing the "
                            f"story changed — `publishes:` belongs on the story that introduces the event; this "
                            f"story drops the line")
            continue
        if not raisers:
            problems.append(f"`{event}` is declared in {declared[0]}, but nothing {scope} refers to it — the "
                            f"aggregate raises it or the use case publishes it")
            continue
        found.append(f"{event} (declared in {declared[0]}, raised in {raisers[0]})")
    if problems:
        result.fail("outcome", "; ".join(problems))
    else:
        result.ok("outcome", "the outcome event exists: " + "; ".join(found))


#: The sections of a discovery report, in order (WP-85) — the craft's five parts, the proposed work and the sources.
DISCOVERY_SECTIONS = ("Problem", "Users and evidence", "Options", "Outcome", "Risks and open questions",
                      "Proposed work", "Sources")


#: The fields every proposed body of work carries before it can become an epic; `domain_contact` may stay `open`.
DISCOVERY_FIELDS = ("intent", "goal", "metric")


#: An optional section between the proposed work and the sources: a change the findings make to the project
#: description, one `### <file> — <section>` each with `- change:`. Discover writes it, never the description:
#: a released change goes through the description skill.
DESCRIPTION_CHANGES = "Proposed description changes"


DESCRIPTION_FILES = ("product.md", "tech.md", "domain.md")


def discovery_items(text, section):
    """The `### <name>` blocks of one `## <section>` of a discovery report: [(name, {field: value})]."""
    marker = f"\n## {section}"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1].split("\n## ", 1)[0]
    return [(item.splitlines()[0].strip(),
             {k.lower(): v for k, v in re.findall(r"^\s*-\s*([A-Za-z_]+):\s*(.*?)\s*$", item, re.M)})
            for item in re.split(r"^### ", body, flags=re.M)[1:]]


SOURCE_LINE = re.compile(r"^\s*-\s*\[(S\d+)\]\s*(.+?)\s*$")


CITATION = re.compile(r"\[(S\d+)\]")


READ_ON = re.compile(r"\bread \d{4}-\d{2}-\d{2}\b")


def check_discovery(result, cwd, profile, topic):
    """`project/discovery/<topic>/discovery.md`: the sections in order, every citation a listed source, every
    source resolving — an excerpt under the topic's folder, a project file, or a URL with the date it was read —
    every proposed body of work with intent, goal and metric, and the topic's `originals/` ignored by git."""
    folder = os.path.join(location(profile, "discovery"), topic).replace(os.sep, "/")
    report = f"{folder}/discovery.md"
    if not os.path.isfile(os.path.join(cwd, report)):
        result.fail("discovery", f"no {report} — `factory-discover {topic}` writes it")
        return
    text = read_text(os.path.join(cwd, report))
    headings = [h.strip() for h in re.findall(r"^## (.+)$", text, re.M)]
    missing = [h for h in DISCOVERY_SECTIONS if h not in headings]
    order = [h for h in headings if h in DISCOVERY_SECTIONS]
    problems = []
    if missing:
        problems.append("missing " + ", ".join(f"`## {h}`" for h in missing))
    elif order != list(DISCOVERY_SECTIONS):
        problems.append("the sections are out of order — " + " → ".join(DISCOVERY_SECTIONS))
    sources = {}
    for line in (section_of(text, "sources") or []):
        match = SOURCE_LINE.match(line)
        if match:
            sources[match.group(1)] = match.group(2)
    body = text.split("\n## Sources", 1)[0]
    unknown = sorted(set(CITATION.findall(body)) - set(sources), key=lambda c: int(c[1:]))
    if unknown:
        problems.append("cited but not under `## Sources`: " + ", ".join(f"[{c}]" for c in unknown))
    for sid, entry in sources.items():
        url = re.search(r"https?://\S+", entry)
        if url:
            if not READ_ON.search(entry):
                problems.append(f"{sid}: a web source names the date it was read (`read YYYY-MM-DD`)")
            continue
        paths = [bare_path(p) for p in re.findall(r"`([^`]+)`", entry)] or \
            [bare_path(p) for p in re.findall(r"(?<!\S)([\w.-]+/[\w./-]+\.[A-Za-z0-9]{1,6}(?::L?\d+(?:[-–:]\d+)?)?)", entry)]
        if not paths:
            problems.append(f"{sid}: names no file and no URL")
            continue
        for path in paths:
            if not (os.path.isfile(os.path.join(cwd, folder, path)) or os.path.isfile(os.path.join(cwd, path))):
                problems.append(f"{sid}: {path} is not there — an excerpt lives under {folder}/sources/")
    items = discovery_items(text, "Proposed work")
    if "Proposed work" in headings and not items:
        problems.append("`## Proposed work` proposes nothing — one `### <id>` per body of work, or a line saying why none")
    for name, fields in items:
        lacking = [f for f in DISCOVERY_FIELDS if not fields.get(f) or fields[f].lower() == "open" or "{{" in fields[f]]
        if lacking:
            problems.append(f"proposed `{name}` lacks {', '.join(lacking)}")
    if DESCRIPTION_CHANGES in headings:
        # the position is a finding only when both neighbours are there — a missing one is reported above
        if "Proposed work" in headings and "Sources" in headings and \
                not headings.index("Proposed work") < headings.index(DESCRIPTION_CHANGES) < headings.index("Sources"):
            problems.append(f"`## {DESCRIPTION_CHANGES}` stands between `## Proposed work` and `## Sources`")
        changes = discovery_items(text, DESCRIPTION_CHANGES)
        if not changes:
            problems.append(f"`## {DESCRIPTION_CHANGES}` proposes nothing — one `### <file> — <section>` per change, "
                            f"or leave the section out")
        for name, fields in changes:
            if not any(name.startswith(f) for f in DESCRIPTION_FILES):
                problems.append(f"description change `{name}` names none of {', '.join(DESCRIPTION_FILES)} — "
                                f"`### <file> — <section>`")
            if not fields.get("change") or "{{" in fields["change"]:
                problems.append(f"description change `{name}` says no `- change:`")
    ignore = os.path.join(cwd, folder, ".gitignore")
    if not (os.path.isfile(ignore) and re.search(r"^/?originals/?\s*$", read_text(ignore), re.M)):
        problems.append(f"{folder}/.gitignore does not ignore `originals/` — the handed-over originals stay out of git")
    if problems:
        result.fail("discovery", f"{report}: " + "; ".join(problems))
    else:
        changes = len(discovery_items(text, DESCRIPTION_CHANGES))
        result.ok("discovery", f"{report}: {len(DISCOVERY_SECTIONS)} sections, {len(sources)} source(s) resolving, "
                               f"{len(items)} proposed body(ies) of work"
                               + (f", {changes} proposed description change(s)" if changes else ""))


def read_mapping(runs, story_id):
    """criterion key -> list of test selectors, from the gate:tests table."""
    path = os.path.join(runs, story_id, "tests.md")
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


def check_mapping(result, runs, story_id, criteria):
    try:
        path, mapping = read_mapping(runs, story_id)
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


def in_package(paths, cls):
    """The files that hold `cls` itself: where the selector names a package or namespace, a file of that
    simple name declaring another one is a different class — `a.WidgetTest` is not `b.WidgetTest`."""
    if "." not in cls:
        return paths
    wanted = cls.rsplit(".", 1)[0]
    declared = {}
    for path in paths:
        match = re.search(r"^\s*(?:package|namespace)\s+([\w.]+)", read_text(path) if os.path.isfile(path) else "", re.M)
        declared[path] = match.group(1) if match else None
    if not any(declared.values()):
        return paths                          # nothing declares a package: a module path, or a stack without one
    return [path for path in paths if declared[path] == wanted
            or (declared[path] is None and wanted.replace(".", "/") in path.replace(os.sep, "/"))]


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
            candidates = in_package(sources.get(simple, []), cls)
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


# Commands whose shell could not find their program, in the order they were met. A missing tool is the
# environment's fault, not the story's: the report names it as `environment`, and the runner stops once
# on it instead of sending a stage into rounds it cannot win.
MISSING_TOOLS = []


MISSING_TOOL = re.compile(r"(?:^|\n)(?:[^\n:]*: )?(?:line \d+: |\d+: )?([^\s:]+): (?:command )?not found"
                          r"|'([^']+)' is not recognized as an internal or external command")


def missing_tool(code, output):
    """The program a shell could not find (exit 127, or cmd.exe's 9009), else None."""
    if code not in (127, 9009):
        return None
    found = MISSING_TOOL.search(output or "")
    return (found.group(1) or found.group(2)) if found else "a program"


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
SUITES_RECORD = None


def suites_tree_key(cwd, runs):
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


def suites_signature(key, tree, invocation, code, ran_json):
    return hmac.new(key.encode("utf-8"), f"{tree}\t{invocation}\t{code}\t{ran_json}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def open_suites_record(cwd, runs, story_id, key):
    """The rows of `.verify/suites.tsv` for this tree whose signature the runner's key confirms. A row
    written by anything else — a stage, a hand — carries no valid signature and is not read."""
    path = os.path.join(evidence_dir(runs, story_id), "suites.tsv")
    tree = suites_tree_key(cwd, runs)
    rows = {}
    if tree and os.path.isfile(path):
        for line in read_text(path).splitlines():
            parts = line.split("\t")
            if len(parts) != 6:
                continue
            when, row_tree, invocation, code, ran_json, signature = parts
            if row_tree == tree and hmac.compare_digest(
                    signature, suites_signature(key, row_tree, invocation, code, ran_json)):
                rows[invocation] = (when, int(code), json.loads(ran_json))
    return {"path": path, "key": key, "tree": tree, "rows": rows}


def recorded_run(invocation, cwd, profile=None, with_reports=False):
    """(code, output, ran, reused) — the invocation run now, or the runner's own record of it on this tree.

    Only a run that passed is recorded: a red run is run again, so a fix is seen by the run that judges
    it. `ran` is what the reports of the run said was executed (empty when `with_reports` is off), and
    `reused` is the suffix that tells the reader the verdict came from the record."""
    record = SUITES_RECORD
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


#: The judge's built-in perspectives — part of the method, never switched off; `reviews:` in the profile adds more.
BUILT_IN_PERSPECTIVES = ("ddd", "hexagonal", "clean-code")


#: A review report carries its findings under these ranks (the review skills' own format).
REVIEW_RANKS = ("must-fix", "should-fix", "nit")


def perspectives_of(profile):
    """`(name, carrier)` per perspective: the three built-ins and the profile's `reviews:`, each with the skill
    `review.<name>:` names — the plugin prefix dropped — or `review-<name>` where the profile names none."""
    names = list(BUILT_IN_PERSPECTIVES)
    for extra in re.split(r"[,\s]+", str(profile.get("reviews", "")).strip()):
        if extra and extra not in names:
            names.append(extra)
    out = []
    for name in names:
        carrier = str(profile.get(f"review.{name}", "")).split()
        out.append((name, (carrier[0].rsplit(":", 1)[-1] if carrier else f"review-{name}")))
    return out


def check_reviews(result, runs, story_id, profile):
    """One review file per perspective, `reviews/<name>.md`, in the review skills' report format. A missing
    file is a note — the judge then ran that pass itself and says so — a file without a findings section is
    not a review and is refused: the judge would converge from nothing while the report claims a perspective."""
    folder = os.path.join(runs, story_id, "reviews")
    read, missing, malformed = [], [], []
    for name, _carrier in perspectives_of(profile):
        path = os.path.join(folder, f"{name}.md")
        if not os.path.isfile(path):
            missing.append(name)
            continue
        text = read_text(path).lower()
        if not any(rank in text for rank in REVIEW_RANKS) and "nothing found" not in text and "no finding" not in text:
            malformed.append(name)
            continue
        read.append(name)
    if malformed:
        result.fail("reviews", f"reviews/{', reviews/'.join(malformed)}.md carries no must-fix, should-fix or nit "
                               f"section and says of no finding that there is none — not a review report")
        return
    if missing:
        result.note("reviews", f"no review file for {', '.join(missing)} (reviews/<perspective>.md) — the judge ran "
                               f"that pass itself, and `## Perspectives covered` says so")
    if read:
        result.ok("reviews", f"{len(read)} review file(s) for the judge to converge from: {', '.join(read)}")


#: What a hand-over has to say fits in this many bytes for a story of n criteria: a base and a share per
#: criterion, set from the bench's stories (the leanest files carried what the next stage needed at these
#: sizes; the largest were half again as big and said nothing more). A note, never a refusal: the number
#: is the measure `--contract` names, a stage with a reason writes it, and the measurement decides.
HANDOVER_BUDGET = {"plan.md": (3000, 300), "tests.md": (1500, 200), "build.md": (1500, 150),
                   "tidy.md": (1500, 0), "judge.md": (3000, 100), "document.md": (2500, 150)}


#: Sections the pipeline writes into a hand-over; their bytes are not the stage's and do not count against
#: its measure — a skeleton's `## Paths` alone ran to 1.5 kB in the bench.
PIPELINE_SECTIONS = {"document.md": ("## Paths",)}


def stage_bytes(path, name):
    """The bytes of a hand-over that the stage wrote: the file without the sections the pipeline put there."""
    text = read_text(path)
    for heading in PIPELINE_SECTIONS.get(name, ()):
        start = text.find("\n" + heading)
        if start < 0:
            continue
        end = text.find("\n## ", start + 1)
        text = text[:start] + (text[end:] if end >= 0 else "")
    return len(text.encode("utf-8"))


def check_size(result, runs, story_id, files, count):
    """A note when a hand-over is larger than what it has to say for a story of `count` criteria."""
    for name in files:
        path = os.path.join(runs, story_id, name)
        if name not in HANDOVER_BUDGET or not os.path.isfile(path):
            continue
        base, per = HANDOVER_BUDGET[name]
        budget = base + per * count
        size = stage_bytes(path, name)
        if size > budget:
            result.note("size", f"{name} is {size / 1000:.1f} kB of the stage's own text; what it has to say for {count} "
                                f"criteria fits in {budget / 1000:.1f} kB (the contract's measure): keys and levels, not "
                                f"the story's text; one citation per row; nothing the story, the plan or the code already "
                                f"says. A note, not a refusal — never a reason to edit the file after the gate ran")


def check_compiles(result, profile, cwd):
    command = profile.get("compile")
    if not command:
        result.skip("compiles", "no `compile:` command in the stack profile")
        return
    code, output, _ran, reused = recorded_run(command, cwd)
    if code == 0:
        result.ok("compiles", f"`{command}` succeeded{reused}")
    else:
        result.fail("compiles", f"`{command}` failed:\n{tail(output)}")


#: A markdown table row, split into its cells. The first cell names the thing, the **last**
#: names how it was checked — the tables differ in width, so counting from the left is wrong.
PATHLIKE = re.compile(r"`([\w./-]+\.[A-Za-z0-9]{1,6}(?::L?\d+(?:[-–:]\d+)?|#[\w.-]+)?)`")


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


def check_story_pass(result, runs, story_id, story_path, front):
    """The document gate delivers a story, so it asks what delivery rests on: every stage of this pass
    wrote its file after the one before it, the judge passed it, and the story is the one that was planned.
    A document written for an earlier pass, or over a judge who asked for changes, delivers nothing."""
    order = JOURNEY_ORDER if story_kind(front) == "journey" else STAGE_ORDER
    folder = os.path.join(runs, story_id)
    texts = current_stage_files(runs, story_id, order)
    gaps = [f"{STAGE_FILES[s]} ({'written for an earlier pass' if os.path.isfile(os.path.join(folder, STAGE_FILES[s])) else 'missing'})"
            for s in order if s not in texts]
    if gaps:
        result.fail("story-pass", f"{', '.join(gaps)} — the document gate delivers a story whose stages all ran, "
                                  f"in order, in this pass; the story runs on from the first of them")
        return
    verdict = verdict_in(texts["judge"])
    if verdict != "pass":
        result.fail("story-pass", f"{STAGE_FILES['judge']} says `verdict: {verdict or 'none'}` — only a judge's "
                                  f"`pass` lets a story be delivered")
        return
    planned = os.path.join(evidence_dir(runs, story_id), STORY_DIGEST)
    if not os.path.isfile(planned):
        result.skip("story-pass", f"no {STORY_DIGEST} from the plan gate — whether the story changed since it was "
                                  f"planned is not checked")
        return
    if read_text(planned).strip() != story_digest(story_path):
        result.fail("story-pass", f"{story_path} changed after it was planned — a criterion no stage planned, "
                                  f"tested or built cannot be delivered; the story runs again from plan")
        return
    result.ok("story-pass", f"every stage of this pass ran in order, the judge passed it, and the story is the "
                            f"one that was planned")


def check_documented(result, runs, story_id, cwd):
    """The document stage may only write statements that can be checked. Two of them can be
    checked here: a file it says it updated exists, and every glossary row names where its
    definition came from. A documented path that does not resolve outlives the story."""
    path = os.path.join(runs, story_id, "document.md")
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
        # A path, or a bare file name with a line (`BookId.java:8`) — that is a citation, and a
        # citation resolves from the project root or sends the reader nowhere.
        if ("/" in target or target != name) and not os.path.exists(os.path.join(cwd, target)):
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


def check_stage_commands(result, profile, cwd, stage):
    """The gate must not *know* its checks, it looks them up. Adding a capability is
    then one line in the profile, not an edit to a stage."""
    for key in STAGE_CHECKS.get(stage, ()):
        command = profile.get(key)
        if not command:
            result.skip(key, f"no `{key}:` command in the stack profile")
            continue
        code, output, _ran, reused = recorded_run(command, cwd)
        if code == 0:
            result.ok(key, f"`{command}` succeeded{reused}")
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


def joined_filter(profile, flag, patterns):
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


def check_test_state(result, profile, cwd, mapping, expected, located=None, runs=None, story=None, guard=False,
                     whole_for=(), red_proof=True):
    """expected 'red': every mapped test must fail. 'green': all must pass. A `guard` — a journey over
    delivered stories — is green without ever having been red: its steps exist before it is written.

    One process per test command, not per selector: every selector a command covers goes into one
    invocation, and each selector's verdict is read from that run's reports by name. A command in
    `whole_for` (the policy's `required:` commands at the build and tidy gates) runs whole instead, and
    the run is returned — `{command: (key, code, output, ran)}` — so the suite check reads it rather than
    running the same command again. `testEvidence: exit-code` keeps one process per selector: it has no
    report to read a name from. `red_proof=False` leaves the red proof to a caller that checked it before
    any process started — it is a digest comparison, not a run."""
    fallback = profile.get("e2eTest") or profile.get("test")
    flag = profile.get("filterFlag", "")
    fmt = profile.get("filterFormat", "{class}.{method}")
    located = located or {}
    whole_for = set(whole_for or ())
    whole_runs = {}
    if not fallback:
        result.skip(
            f"tests-{expected}",
            "no `e2eTest:` or `test:` command in the stack profile",
        )
        return whole_runs
    if not mapping:
        return whole_runs
    ledger = red_ledger_path(runs, story)
    have_ledger = bool(ledger) and os.path.isfile(ledger)
    was_red = read_red_ledger(runs, story)
    red_digests = read_red_digests(runs, story)
    now_red = set()
    kept = {}                                 # entries an earlier run made that this run leaves as they are
    # An expectation that changes on a human's decision: the test was recorded red before the code
    # existed, the decision changed what it expects, and the code now meets it. Only that combination
    # lets a green test through the red check — without the decision it is the refusal below.
    changed_on = answered_decisions(cwd, story, "test") if expected == "red" else []
    if expected == "red":
        # A story that runs again for a human's correction keeps the criteria it had already met:
        # their tests were red once, for this very story, and are green now for that reason.
        with contextlib.suppress(GateError):
            changed_on += [rid for rid, _f, state, answer, _b in acceptance_records(cwd, story)
                           if state in ("answered", "applied") and not accepted(answer)]
    # A story planned again — its text changed, a story conflict was answered — keeps the criteria its
    # earlier pass already built: their tests were seen red for this story, and a build made them green.
    built_before = bool(runs and story) and os.path.isfile(os.path.join(runs, story, STAGE_FILES["build"]))
    by_report = profile.get("testEvidence", "").strip() != "exit-code"

    # 1. Every selector resolves to the command that covers it — or to a configuration fail — before
    #    anything runs. Grouped by command, one process then carries every selector it covers.
    groups = {}
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
            groups.setdefault(command, []).append((key, selector, cls, method, test_path, command_key, pattern))

    def observed_run(invocation):
        """(code, output, {(class, method): outcome}, reused) of one invocation, from the reports it
        wrote — or from the runner's record of the same invocation on this tree."""
        return recorded_run(invocation, cwd, profile, with_reports=True)

    def verdict(key, selector, command_key, passed, output, evidence):
        """The selector's verdict against what the ledger and the stage expect — unchanged by how it ran."""
        if not passed:
            now_red.add(selector)
        if expected == "green" and passed and guard:
            result.ok("tests-green", f"{selector} passes — a journey guards what is delivered ({key})")
            return
        if expected == "green" and passed and not have_ledger:
            # No test stage ran in this checkout — the run artefacts may simply not be
            # committed. Say that the evidence is missing instead of inventing either verdict.
            result.skip(
                "tests-green",
                f"{selector} is green, but no `{os.path.basename(ledger)}` from a test stage "
                f"is present here, so nothing proves it ever failed ({key!r}).",
            )
            return
        if expected == "green" and passed and selector not in was_red:
            # Never seen red: a runner that matched nothing exits 0 exactly like a passing
            # test, so "green" alone is no evidence that this test ran at all.
            result.fail(
                "tests-green",
                f"{selector} passes now but was never recorded red by the test stage "
                f"({key!r}) — a test that never failed proves nothing, and a run that "
                f"matched no test passes too. Run `--stage test` before the build stage.",
            )
            return
        if expected == "red" and passed and selector in was_red and changed_on:
            now_red.add(selector)
            result.ok("tests-red", f"{selector} is green now and was recorded red before; its "
                                   f"expectation changed on decision {', '.join(changed_on)} ({key})")
            return
        if expected == "red" and passed and selector in was_red and built_before:
            recorded = red_digests.get(selector)
            test_file = located.get(selector)
            if recorded and test_file and os.path.isfile(os.path.join(cwd, test_file)) \
                    and file_digest(os.path.join(cwd, test_file)) != recorded:
                # Changed after its build met it — the judge sent it back as asserting too little. It is
                # green and can never be seen red again: one change to the code that turns it red shows
                # that the new assertion bites.
                probe = Result()
                check_break(probe, profile, cwd, runs, story, selector, key, located)
                result.entries.extend(probe.entries)
                if not probe.failed:
                    now_red.add(selector)
                else:
                    # The earlier proof stands for the version it was taken against; losing it would make
                    # the next run treat this test as one never seen red, which no break can repair.
                    kept[selector] = recorded
                return
            now_red.add(selector)
            result.ok("tests-red", f"{selector} is green now and was recorded red in an earlier pass of this "
                                   f"story, whose build met it ({key})")
            return
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

    # 2. One process per command. Where the policy runs the command whole at this gate anyway, the whole
    #    run is the evidence for its selectors too; elsewhere every selector goes into one filtered run.
    control = {}                              # one control run per command, not per selector
    for command, items in groups.items():
        command_key = items[0][5]
        patterns = list(dict.fromkeys(item[6] for item in items))
        if not by_report:
            # `testEvidence: exit-code`: the exit code is all there is, and it belongs to one selector.
            for key, selector, cls, method, test_path, command_key, pattern in items:
                invocation = f'{command} {flag} "{pattern}"'.strip()
                code, output = run(invocation, cwd)
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
                verdict(key, selector, command_key, code == 0, output, "")
                if expected == "red" and code != 0 and red_on_timeout(output):
                    timeout_note(result, expected, selector)
            continue
        whole = command_key in whole_for
        invocation = command if whole else f"{command} {joined_filter(profile, flag, patterns)}".strip()
        code, output, ran, reused = observed_run(invocation)
        if whole:
            whole_runs[command] = (command_key, code, output, ran)
        shared = whole or len(patterns) > 1
        timed_out = []
        for key, selector, cls, method, test_path, command_key, pattern in items:
            display = display_name_of(test_path, method)
            outcome, how = outcome_for(ran, cls, method, display)
            item_output = output
            if outcome is None and shared:
                # Not in the shared run's report. Before that fails the selector it runs alone, once: a
                # runner that honours one filter and drops the second, or a whole run that skipped a
                # source set, must not fail a test that a run of its own would show.
                alone = f'{command} {flag} "{pattern}"'.strip()
                code_alone, item_output, ran_alone, reused = observed_run(alone)
                outcome, how = outcome_for(ran_alone, cls, method, display)
                if outcome is not None:
                    result.note(f"tests-{expected}",
                                f"{selector}: absent from the report of `{invocation}`, run alone (`{alone}`) — "
                                f"a runner that drops a joined filter costs one process per selector here")
            if outcome is None:
                detail = (f" — {how}" if how else
                          f" ({len(ran)} case(s) in the report(s) written by this run)")
                result.fail(
                    f"tests-{expected}",
                    f"{selector}: no test report from this run shows it ran{detail}. Let the "
                    f"runner write one (JUnit XML is the default on the JVM; .NET needs "
                    f"`--logger trx`), point `testReport:` at it, give the test a name the "
                    f"report carries, or accept the weaker check with "
                    f"`testEvidence: exit-code`:\n{tail(item_output)}",
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
            passed = outcome == "passed"
            verdict(key, selector, command_key, passed, item_output, f"report {how}{reused}")
            if expected == "red" and not passed and red_on_timeout(item_output):
                timed_out.append(selector)
        if timed_out and shared:
            # One output for the run: which of its red tests hit the timeout is not readable from it.
            result.note(f"tests-{expected}", f"`{invocation}`: red on a timeout, not on an assertion, somewhere "
                                             f"among {', '.join(timed_out)} — an action waited for something that "
                                             f"is not there; the first step that can be missing should be an "
                                             f"expectation (`expect(locator).toBeVisible()` before the click or "
                                             f"fill), so the failure names it.")
        else:
            for selector in timed_out:
                timeout_note(result, expected, selector)
    if expected == "red":
        write_red_ledger(runs, story, now_red, located, cwd, kept)
    elif have_ledger and red_proof:
        check_red_proof(result, cwd, located, read_red_digests(runs, story), story)
    return whole_runs


def timeout_note(result, expected, selector):
    result.note(f"tests-{expected}", f"{selector} is red on a timeout, not on an assertion — an action "
                                     f"waited for something that is not there. Red is red, but it says "
                                     f"nothing about what is missing: the first step that can be missing "
                                     f"should be an expectation (`expect(locator).toBeVisible()` before "
                                     f"the click or fill), so the failure names it.")


#: What a browser runner prints when an action, not an expectation, ran out of time.
TIMEOUT_RED = re.compile(r"TimeoutError|Timeout \d+ms exceeded|TimeoutException")


ASSERTION_RED = re.compile(r"expect\(|AssertionError|AssertionFailedError|Expected\b|assert", re.IGNORECASE)


def red_on_timeout(output):
    """A red that came from an action's timeout with no expectation in sight."""
    return bool(TIMEOUT_RED.search(output or "")) and not ASSERTION_RED.search(output or "")


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
def red_ledger_path(runs, story):
    if not runs or not story:
        return None
    return os.path.join(evidence_dir(runs, story), ".tests-red")


def read_red_digests(runs, story):
    """{selector: sha256 of its test file when it was recorded red, or None for an older ledger}.

    A red proof is a proof about one version of a test. The digest binds it to that version, so a
    test weakened after it was seen failing no longer carries the proof into the build gate."""
    path = red_ledger_path(runs, story)
    if not path or not os.path.isfile(path):
        return {}
    digests = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            selector, _, digest = line.strip().partition("\t")
            if selector:
                digests[selector] = digest.strip() or None
    return digests


def read_red_ledger(runs, story):
    return set(read_red_digests(runs, story))


def write_red_ledger(runs, story, selectors, located=None, cwd=".", kept=None):
    """The red record: every selector seen red now, bound to its test file's digest — and, in `kept`, the
    entries an earlier run made that this run could neither confirm nor replace (a strengthened test whose
    break is still missing keeps its old proof, so the next run can prove the new version instead of
    treating a test it once saw red as one it never did)."""
    path = red_ledger_path(runs, story)
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


def tail(output, limit=1200):
    text = output.strip()
    return text[-limit:] if len(text) > limit else text


def check_decisions(result, runs, story_id, cwd, gating=None, story_path=None):
    """Every question this story raised is recorded, and every answer it got has been applied.

    Runs on every stage: an open question blocks the story wherever it stands, and a stage file
    that escalates without a record has asked nobody. `gating` is the stage this gate call is for:
    the plan gate runs *before* its stage, so there an answered plan question is the stage's input,
    not yet something it failed to apply."""
    try:
        store = decisions_store(story_path or find_story(place("epics"), story_id))
        records = read_decisions(store, story_id)
    except GateError as error:
        result.fail("decisions", str(error))
        return
    known = {str(front["id"]).strip(): (path, body, state) for path, front, body, state, _ in records}

    # 1. a stage that stopped must have written a record for its question
    stage_texts = {}
    for stage, name in STAGE_FILES.items():
        path = os.path.join(runs, story_id, name)
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
                f"record under {shown(store)}/ so an answer has a place to land; without one, "
                f"nobody was asked.",
            )
        for wanted in ids:
            if wanted not in known:
                result.fail(
                    "decisions",
                    f"{path}: `## needs-human` names decision {wanted!r}, but "
                    f"{shown(record_path(story_id, wanted, story_path))} does not exist or names another story.",
                )

    # 2. every record: open blocks, a draft is still open, answered must be applied by its stage.
    # An acceptance record is the document gate's own question; that gate reads it.
    for path, front, body, state, answer in records:
        if is_acceptance(front):
            continue
        rid = str(front["id"]).strip()
        stage = str(front.get("stage", "")).strip() if state in ("open", "draft") else resume_stage(front, answer)
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
                    f"{os.path.join(runs, story_id, STAGE_FILES.get(stage, '?'))} does not cite "
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


# The same checks outside a story: a direct edit, a commit and CI get one verdict for one tree. The
# profile declares the commands; its `required:` line declares which of them must hold. Without
# that line the check reports what it ran and what it skipped, and fails only on a red command.
CHANGE_CHECKS = ("compile", "test", "architecture", "format")


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
    code, output, ran, reused = recorded_run(command, cwd, profile, with_reports=True)
    judge_test_run(result, profile, key, command, code, output, ran, required, strict, reused=reused)


def judge_test_run(result, profile, key, command, code, output, ran, required, strict=False, reused=""):
    """The verdict on one run of a test command, from its exit code and the reports it wrote.
    `reused` names where the run came from when this check did not start it."""
    executed = sum(1 for outcome in ran.values() if outcome != "skipped")
    failed = sum(1 for outcome in ran.values() if outcome == "failed")
    if code != 0 or failed:
        red(result, "test", f"`{command}` ({key}) failed — {failed} failing case(s):\n{tail(output)}",
            required, strict)
    elif executed:
        result.ok("test", f"`{command}` ({key}) ran {executed} case(s), none failed{reused}")
    elif profile.get("testEvidence") == "exit-code":
        result.skip("test", f"`{command}` ({key}) exited 0 and writes no report "
                            f"(`testEvidence: exit-code`) — nothing shows a test ran")
    else:
        message = (f"`{command}` ({key}) exited 0, but no report written by this run shows an "
                   f"executed test — a runner that matched nothing exits 0 too")
        (result.fail if required else result.note if strict else result.skip)("test", message)


# A story may add tests and add cases to a test file; it may not change what a test that existed
# before it expects, unless a human decided that. The plan gate runs before any stage of the story
# touches a test, so it records the test files as git blobs; later gates compare against them.
TESTS_BASELINE = ".tests-baseline"


TEST_FILE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go|rb|exs?)$|Tests?\.(java|kt|cs|scala|groovy)$|IT\.(java|kt)$"
    r"|Spec\.(scala|groovy|kt)$|\.(test|spec)\.(js|jsx|ts|tsx|mjs)$|_spec\.rb$)")


SKIP_DIRS = {".git", "build", "target", "bin", "obj", "node_modules", "dist", ".gradle",
             ".agents", ".claude", ".codex", ".opencode", "__pycache__", ".venv", "venv"}


def test_files(cwd):
    found = []
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith("."))
        for name in sorted(files):
            if TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


def record_tests_baseline(cwd, runs, story_id):
    """Write the baseline once per story; a later plan gate must not launder a change into it."""
    path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
    if os.path.isfile(path) or git(cwd, "rev-parse", "--git-dir")[0]:
        return
    files = test_files(cwd)
    blobs = []
    for rel in files:
        code, blob = git(cwd, "hash-object", "-w", "--", rel)
        if code == 0:
            blobs.append(f"{blob}  {rel}")
    write_mark(runs, story_id, TESTS_BASELINE, "\n".join(blobs))


def human_line(text):
    """A line a person wrote: not empty, not "none", not a template placeholder or an HTML comment."""
    text = re.sub(r"<!--.*?-->", "", text).strip()
    return bool(text) and text.lower() not in NOTHING and "{{" not in text


def changed_tests_in_plan(runs, story_id):
    """{test file: backed-by cell} from the plan's `## Changed tests` table."""
    path = os.path.join(runs, story_id, "plan.md")
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


#: A statement that checks: an assertion library's call, a framework's expectation, a mock's verification.
ASSERTION_STATEMENT = re.compile(r"\b(?:assert\w*|expect\w*|andExpect\w*|verify\w*|should\w*)\b", re.IGNORECASE)


TOKEN = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\w+")


def statements(text):
    """The statements of a test source, each as its word and literal tokens: split at `;`, at a brace, and at a line
    end outside brackets unless the next line goes on with `.` (a call chain) — the shapes Java, C#, Kotlin, JS and
    Python test files are written in."""
    out, current, depth, quote, escaped = [], [], 0, "", False
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


def assertions_kept(before, now):
    """Whether every assertion the old test made is still made: each old assertion statement's tokens appear, in
    order, in a statement of the new version that is an assertion too — more arguments, never fewer, never another
    expected value. A changed arrangement (a constructor that gained a field, a renamed local) passes; a changed
    expectation, a removed assertion or a weaker matcher does not."""
    old = [tokens for tokens in statements(before) if ASSERTION_STATEMENT.search(" ".join(tokens))]
    new = [tokens for tokens in statements(now) if ASSERTION_STATEMENT.search(" ".join(tokens))]
    if not old:
        return False
    def within(small, large):
        rest = iter(large)
        return all(any(token == other for other in rest) for token in small)
    used = set()
    for tokens in old:
        match = next((i for i, candidate in enumerate(new) if i not in used and within(tokens, candidate)), None)
        if match is None:
            return False
        used.add(match)
    return True


def switched_off(before, now):
    """Whether the new version carries more skip markers than the old one."""
    count = lambda lines: sum(1 for line in lines if SKIP_MARKER.search(line))
    return count(now) > count(before)


def stage_windows(runs, story_id):
    """(start, end) of every stage window in the story's journal, as epoch seconds; an open one ends now."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    windows, open_ = [], {}
    if not os.path.isfile(journal):
        return windows
    stamp = lambda text: calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S"))
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


def committed_by_a_stage(cwd, runs, story_id, rel):
    """Whether a commit that changed `rel` was made inside one of the story's stage windows. A stage commits
    nothing; a commit in its window is the stage's change, and the story is held to it like any other."""
    windows = stage_windows(runs, story_id)
    if not windows:
        return False
    code, out = git(cwd, "log", "--format=%ct", "-n", "50", "--", rel)
    if code:
        return False
    return any(start - 1 <= int(t) <= end + 1 for t in out.split() if t.isdigit() for start, end in windows)


def decision_covers(cwd, story_id, ids):
    """A test `rel` a decision among `ids` may change: asked by the test or build stage, naming the file, or
    listed by the plan that ran again for it."""
    try:
        records = [(front, body) for _p, front, body, _s, _a in records_of(story_id, cwd=cwd)
                   if str(front["id"]).strip() in ids]
    except GateError:
        records = []

    def covers(rel, planned):
        if rel in planned:
            return True
        return any(getattr(STAGE.get(str(front.get("stage", "")).strip()), "lists", False)
                   or os.path.basename(rel) in body
                   for front, body in records)
    return covers


def check_existing_tests(result, cwd, runs, story_id, story_body=""):
    path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
    if not os.path.isfile(path):
        result.skip("tests-kept", "no baseline of the tests that existed before this story "
                                  "(the plan gate records one in a git repository)")
        return
    changed, lost, arranged = [], [], []
    for line in read_text(path).splitlines():
        if "  " not in line:
            continue
        blob, rel = line.split("  ", 1)
        full = os.path.join(cwd, rel)
        if not os.path.isfile(full):
            changed.append(f"{rel} (removed)")
            continue
        # A run commits nothing while a story is open: a test committed since the baseline changed outside
        # this story. The story is held to its own changes — against what is committed now.
        head_code, head_blob = git(cwd, "rev-parse", f"HEAD:{rel}")
        if not head_code and head_blob.strip() and head_blob.strip() != blob \
                and not git(cwd, "cat-file", "-e", blob)[0] and not committed_by_a_stage(cwd, runs, story_id, rel):
            blob = head_blob.strip()
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
        if switched_off(was, now):
            changed.append(f"{rel} (switched off)")
        elif all(any(old == new for new in remaining) for old in was):
            pass
        elif assertions_kept("\n".join(was), "\n".join(now)):
            arranged.append(rel)
        else:
            changed.append(rel)
    if lost:
        result.skip("tests-kept", f"the baseline of {', '.join(lost)} is gone from the object store (pruned by "
                                  f"`git gc`?) — not compared")
    if arranged:
        result.note("tests-kept", f"{', '.join(arranged)} changed only around its assertions — every assertion it had "
                                  f"is still there, at most with more arguments (a type the test builds gained a field)")
    if not changed:
        result.ok("tests-kept", "no test that existed before this story changed what it expects")
        return
    # A decision changes the tests it is about, not any test: one the test or the build stage asked about a
    # test, one whose record names the file, or — for a plan's question — the tests the re-plan lists.
    decided = answered_decisions(cwd, story_id, "test")
    planned = changed_tests_in_plan(runs, story_id)
    covering = decision_covers(cwd, story_id, decided)
    if decided and all(covering(e.replace(" (removed)", "").replace(" (switched off)", ""), planned) for e in changed):
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
                    records_of(story_id) if state in ("answered", "applied")}
    except GateError:
        answered = set()
    listed = changed_tests_in_plan(runs, story_id)
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


def check_required_suites(result, profile, cwd, already=None):
    """At build and tidy: the test commands the policy requires, run whole.

    The mapped tests say this story's behaviour holds; they say nothing about the behaviour the
    stories before it delivered. Without a policy the stage gates stay as they were. A command the
    test-state check already ran whole (`already`: `{command: (key, code, output, ran)}`) is judged
    from that run — one process per command per gate, not two."""
    already = already or {}
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
        if profile[key] in already:
            _key, code, output, ran = already[profile[key]]
            judge_test_run(result, profile, key, profile[key], code, output, ran, True, True,
                           reused=" (the run the mapped tests were read from)")
        else:
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


# The runner snapshots the working tree before and after every stage (path and sha256 of every file
# git reports as differing from HEAD, untracked ones included, and `deleted` for a tracked file that is
# gone). What a stage changed follows from two snapshots and the list of tracked files,
# deterministically. What the whole story changed follows from two git trees: the one recorded at the
# story's first stage, written without committing anything, and the working tree now — so a project
# without a commit, where `git diff` has nothing to compare against, still gets its diff, and a stage
# run again does not move the story's starting point. Both are written as files the next stage reads
# first, instead of reconstructing them. Paths are relative to the project, which may be a directory
# inside a larger repository.
#: The installed pipeline: every stage reads it, `factory.sh setup` and `update` alone change it. A stage's change
#: there is not hidden as the pipeline's own — it is refused (`pipeline`), because it is the gate judging itself.
PIPELINE_DIR = ".agents/factory/"


def check_pipeline_untouched(result, runs, story_id):
    """No stage of the story changed the installed pipeline: every changed-files record of the story is read, so a
    change made by any stage is refused at the next gate, whichever stage made it. Silent without a record."""
    records = sorted(glob.glob(os.path.join(evidence_dir(runs, story_id), "changed-*.txt")))
    if not records:
        return
    touched = sorted({line.split("\t", 1)[1] for record in records for line in read_text(record).splitlines()
                      if "\t" in line and line.split("\t", 1)[1].startswith(PIPELINE_DIR)})
    if touched:
        result.fail("pipeline", f"a stage changed the installed pipeline: {', '.join(touched[:6])}"
                                f"{' …' if len(touched) > 6 else ''} — a stage reads {PIPELINE_DIR} and never writes "
                                f"it; put it back (`factory.sh update`, or git) and the stage runs again")
    else:
        result.ok("pipeline", f"no stage of {story_id} changed {PIPELINE_DIR}")


def check_files_listed(result, runs, story_id, stage, cwd=".", located=None):
    """The test, build and tidy hand-overs name every file the stage changed, so the next stage can read
    those instead of searching. Checked against the changed-files record, never against the claim.

    A test file the stage put back to the version the test stage saw red is not the stage's change to
    list: the red ledger holds that version's digest, and a file that matches it again was restored,
    not changed — a stage that undid its own edit of a test would otherwise be refused for the undoing."""
    record = os.path.join(evidence_dir(runs, story_id), f"changed-{stage}.txt")
    handovers = [STAGE_FILES[stage]]
    if last_ended(runs, story_id, (stage, "builder")) == "builder":
        # A shared builder ran plan to tidy in one window: its record is the one that holds, and a file it
        # changed is listed by whichever of its hand-overs belongs to the stage that changed it.
        record = os.path.join(evidence_dir(runs, story_id), "changed-builder.txt")
        handovers = [s.file for s in STAGES if s.lists
                     if os.path.isfile(os.path.join(runs, story_id, s.file))]
    base_file = os.path.join(evidence_dir(runs, story_id), "base-tree")
    if window_open(runs, story_id, "builder") and stage in SHARED_WINDOWS["builder"] and os.path.isfile(base_file):
        # A shared builder runs its own gates inside its window, before any changed-files record exists. What the
        # story changed so far is the tree against its base: checked now, the builder can still list a file it
        # forgot — found only by the runner afterwards, it costs a round.
        base = read_text(base_file).strip()
        now = git_tree(cwd) if base and base != "none" else None
        rows = tree_changes(cwd, base, now, runs) if now else None
        if rows is not None:
            record = None
            handovers = [s.file for s in STAGES if s.lists
                         if os.path.isfile(os.path.join(runs, story_id, s.file))]
            changed_now = [path for _kind, path in rows]
    if record is not None and (not os.path.isfile(record) or stage_open(runs, story_id, stage)):
        if stage_open(runs, story_id, stage):
            # A stage that runs its own gate does so inside its window: its record is written at the
            # stage's end, and the gate after `--stage-end` (the orchestrator's, the runner's) checks it.
            result.skip("files-listed", f"the {stage} stage is still open — its changed-files record is written "
                                        f"at its end, and the gate after the stage checks it")
        else:
            result.skip("files-listed", f"no changed-files record for {stage} — the stage was not snapshotted")
        return
    if record is None:
        changed = changed_now
    else:
        reason = snapshot_reason(record)
        if reason:
            result.skip("files-listed", f"the {stage} stage's changes were not observed — {reason}")
            return
        changed = [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
    found = [listed_files(os.path.join(runs, story_id, name)) for name in handovers]
    listed = set().union(*[names for names in found if names is not None]) if any(n is not None for n in found) \
        else None
    if listed is None:
        if not changed:
            # A tidy that found nothing to tidy has nothing to list; the record says so, not the hand-over.
            result.ok("files-listed", f"the {stage} stage changed no file, so {STAGE_FILES[stage]} has nothing to list")
            return
        result.fail("files-listed", f"{STAGE_FILES[stage]} has no `## Files` section (nor a `## Changed` or "
                                    f"`## Moves` table) — list every file the stage changed, one line each")
        return
    missing = [path for path in changed if path not in listed and not any(path.endswith("/" + n) for n in listed)]
    restored = []
    if missing and located:
        digests = read_red_digests(runs, story_id)
        by_file = {test_file: digests.get(selector) for selector, test_file in located.items() if test_file}
        for path in missing:
            digest = by_file.get(path)
            full = os.path.join(cwd, path)
            if digest and os.path.isfile(full) and file_digest(full) == digest:
                restored.append(path)
        missing = [path for path in missing if path not in restored]
    if missing:
        result.fail("files-listed", f"{' / '.join(handovers)} does not list what the stage changed: "
                                    f"{', '.join(missing[:8])}" + (" …" if len(missing) > 8 else ""))
        return
    put_back = (f"; {', '.join(restored)} restored to the version the test stage saw red — a restoration "
                f"is not this stage's change to list") if restored else ""
    unchanged = sorted(n for n in listed if "/" in n and n not in changed
                       and not any(p.endswith("/" + n) or p == n for p in changed))
    if unchanged:
        result.note("files-listed", f"listed but not changed by this stage: {', '.join(unchanged[:5])}")
    result.ok("files-listed", f"{' / '.join(handovers)} list(s) the {len(changed) - len(restored)} file(s) the stage "
                              f"changed{put_back}")


def acceptance_applies(cwd, runs, story_id, profile):
    """Whether this story waits for a human before it is delivered. `pages`: it has a criterion
    whose test the end-user command runs, in a project with a browser — something to look at."""
    mode = acceptance_mode(profile)
    if mode in ("none", "all"):
        return mode == "all"
    if str(profile.get("browser", "none")).strip().lower() in ("", "none"):
        return False
    try:
        _path, mapping = read_mapping(runs, story_id)
    except GateError:
        return False
    located = check_exists(Result(), cwd, mapping) or {}
    return any((command_for(profile, path) or ("", ""))[0] == "e2eTest" for path in located.values())


def ask_acceptance(cwd, runs, story_id, story_path, profile, criteria):
    """Write the next acceptance record beside the story and return its id. The criteria it lists are the
    ones accepted: a reopen after an acceptance compares the story against them."""
    records = acceptance_records(cwd, story_id, story_path)
    number = len(records) + 1
    rid = f"{story_id}-accept-{number}"
    try:
        _path, mapping = read_mapping(runs, story_id)
    except GateError:
        mapping = {}
    run = str(profile.get("run", "")).strip()
    lines = [f"- {key}: {text}" + (f" — `{', '.join(mapping[key])}`" if mapping.get(key) else "")
             for key, text in criteria]
    store = decisions_store(story_path)
    os.makedirs(store, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(store, f"accept-{number}.md"), "w", encoding="utf-8") as handle:
        handle.write(
            f"---\nid: {rid}\nstory: {story_id}\nstage: document\nkind: {ACCEPTANCE_KIND}\n"
            f"asked: {stamp}\ndigest: {story_digest(story_path)}\n---\n\n"
            f"# Accept {story_id}?\n\n## Question\n"
            f"Every gate passed. Look at what the story delivers before it counts as delivered:\n\n"
            + "\n".join(lines) + "\n\n"
            + (f"Start the application with `{run}`.\n\n" if run else
               "Start the application the way the project runs it (the profile names no `run:`).\n\n")
            + "## Options\n"
              "- accepted: the story is delivered.\n"
              "- a correction: what should be different, written into the story (criteria and an "
              "`answered:` line naming this record); the story runs again from plan.\n")
    return rid


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

    def wait(self, check, message):
        """Nothing failed, and a human has to answer before the story goes on — exit 3, not 0."""
        self.entries.append(("wait", check, message))

    @property
    def waiting(self):
        return any(state == "wait" for state, _, _ in self.entries)

    @property
    def failed(self):
        return any(state == "fail" for state, _, _ in self.entries)

    def report(self, story_id, stage, as_json, brief=False):
        if MISSING_TOOLS and not any(check == "environment" for _s, check, _m in self.entries):
            tools = sorted({tool for tool, _c in MISSING_TOOLS})
            self.fail("environment", f"the shell running the gate found no {', '.join(f'`{t}`' for t in tools)} "
                                     f"(`{MISSING_TOOLS[0][1]}`) — the process that runs the gate lacks a tool on "
                                     f"its PATH. No stage can fix that: put it on the PATH, then run the story again")
        if brief:
            # A stage that runs its own gate reads the report into its context: what passed is one line
            # there, what did not stays verbatim — the fail line is the stage's next instruction. The
            # runner's own runs keep the long form, in the report it files for the observer.
            passed = [check for state, check, _ in self.entries if state == "pass"]
            if passed:
                names = sorted(set(passed))
                print(f"gate:pass {len(passed)} check(s) — {', '.join(names)}")
            for state, check, message in self.entries:
                if state != "pass":
                    print(f"gate:{state} {check} — {message}")
        else:
            for state, check, message in self.entries:
                print(f"gate:{state} {check} — {message}")
        skipped = [check for state, check, _ in self.entries if state == "skip"]
        if skipped:
            print(
                f"gate:note stage {stage} ran without {', '.join(sorted(set(skipped)))} — "
                f"a green run here does not cover them"
            )
        verdict = "fail" if self.failed else "wait" if self.waiting else "pass"
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
        return 1 if self.failed else 3 if self.waiting else 0


#: The flags that moved to the CLI beside this file. An older caller — a hook, an instruction file, a
#: skill of an earlier release — is handed over rather than refused; the gate itself does no showing.
MOVED_TO_CLI = frozenset((
    "--list-decisions", "--claim", "--release", "--listening", "--status", "--brief", "--part", "--live",
    "--session-start", "--help-view", "--usage", "--total", "--usage-from", "--usage-model",
    "--window-start", "--window-end", "--stage-start", "--stage-end", "--session-log", "--reopen",
    "--kind", "--resolve", "--start", "--schedule",
))


def hand_over_to_cli(argv):
    """Run the CLI beside this file with the same arguments, where a moved flag is asked of the gate."""
    cli = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "factory-cli.py")
    if not os.path.isfile(cli):
        print(f"gate:fail cli — {' '.join(a for a in argv if a in MOVED_TO_CLI)} moved to factory-cli.py, "
              f"which is not beside this gate; 'factory.sh update' puts it there", file=sys.stderr)
        return 2
    completed = subprocess.run([sys.executable, cli, *argv])
    return completed.returncode


class GateRun:
    """What one gate run over a story knows; the registered checks read it and leave their findings in `result`
    (and the mapping and the located tests for the checks after them)."""

    def __init__(self, **fields):
        self.mapping, self.located = {}, {}
        self.__dict__.update(fields)
        self.kind = story_kind(self.front)
        # a journey is a guard over what is delivered: green at its test gate, the inverse of a story
        self.expected = "red" if self.stage.red and self.kind == "story" else "green"


class Check(typing.NamedTuple):
    name: str
    run: typing.Callable
    stages: tuple
    needs_process: bool
    unrun: typing.Callable       #: the check names a refusal before it leaves unproven


#: The checks a gate run holds a story to, in this order: every check that needs no process first, and a refusal among
#: them ends the run before a suite starts — a file list that is wrong is wrong in a millisecond, not after a minute of
#: tests. What did not run is named, so the report says what is still unproven.
CHECKS = []


def check(name, stages=None, needs_process=False, unrun=None):
    """Register a check against the stage table: `stages` names rows (None — every gated stage) or is a predicate
    over a row."""
    if stages is None:
        chosen = tuple(s.name for s in STAGES if s.gated)
    elif callable(stages):
        chosen = tuple(s.name for s in STAGES if s.gated and stages(s))
    else:
        unknown = [name for name in stages if name not in STAGE or not STAGE[name].gated]
        if unknown:
            raise ValueError(f"check {name}: no gated stage {', '.join(unknown)}")
        chosen = tuple(stages)

    def register(function):
        CHECKS.append(Check(name, function, chosen, needs_process, unrun or (lambda run: [name])))
        return function
    return register


def run_checks(run):
    chosen = [c for c in CHECKS if run.stage.name in c.stages]
    for entry in (c for c in chosen if not c.needs_process):
        entry.run(run)
    process = [c for c in chosen if c.needs_process]
    if run.result.failed and process:
        refused = sorted({check for state, check, _m in run.result.entries if state == "fail"})
        for entry in process:
            for name in entry.unrun(run):
                run.result.skip(name, f"not run — {', '.join(refused)} refused first; fix that, then it runs")
        return
    for entry in process:
        entry.run(run)


@check("story")
def _story(run):
    if not str(run.front.get("context", "")).strip():
        run.result.fail("story", f"{run.story_path}: front matter has no `context:` — a story names the bounded "
                                 f"context it changes")
    else:
        run.result.ok("story", f"{run.story_id} in context {run.front['context']} with {len(run.criteria)} criterion(s)")


@check("contract")
def _contract(run):
    check_contract(run.result, run.profile)


@check("status")
def _status(run):
    check_status(run.result, run.story_path, run.front)


@check("epic")
def _epic(run):
    check_epic(run.result, run.story_path, run.front, run.args.epics)


@check("outcome", stages=("plan",))
def _outcome_named(run):
    check_outcome_named(run.result, run.profile, run.story_path, run.front, run.args.epics)


@check("rounds")
def _rounds(run):
    check_rounds(run.result, run.runs, run.story_id)


@check("suites")
def _suites(run):
    global SUITES_RECORD
    if not run.args.record_suites:
        return
    key = os.environ.get("FACTORY_SUITES_KEY", "")
    if key:
        SUITES_RECORD = open_suites_record(run.cwd, run.runs, run.story_id, key)
    else:
        run.result.note("suites", "--record-suites without FACTORY_SUITES_KEY in the environment — nothing is "
                                  "recorded or reused")


@check("decisions")
def _decisions(run):
    check_decisions(run.result, run.runs, run.story_id, run.cwd, run.stage.name, run.story_path)


@check("plan", stages=("plan",))
def _plan(run):
    check_happy_path(run.result, run.story_path, run.front, run.body, run.profile)
    check_context_map(run.result, run.cwd, run.profile, str(run.front.get("context", "")).strip())
    check_instruction_size(run.result, run.cwd)
    check_project(run.result, run.cwd, run.profile)
    check_models(run.result, run.profile)


@check("document", stages=("document",))
def _document(run):
    check_story_pass(run.result, run.runs, run.story_id, run.story_path, run.front)
    check_outcome_raised(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front)
    check_documented(run.result, run.runs, run.story_id, run.cwd)
    check_proposals_landed(run.result, run.runs, run.story_id, run.cwd, run.profile)
    check_reviews(run.result, run.runs, run.story_id, run.profile)


@check("pipeline", stages=lambda s: s.name != "plan")
def _pipeline(run):
    check_pipeline_untouched(run.result, run.runs, run.story_id)


@check("owned")
def _owned(run):
    check_owned(run.result, run.runs, run.story_id, run.story_path)


@check("adopt", stages=("adopt",))
def _adopt(run):
    check_adopt(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front, run.criteria)


@check("integrate", stages=("integrate",))
def _integrated(run):
    check_integrated(run.result, run.cwd, run.runs, run.story_id)


@check("tests-mapped", stages=lambda s: s.tested)
def _mapping(run):
    run.mapping = check_mapping(run.result, run.runs, run.story_id, run.criteria)
    run.located = check_exists(run.result, run.cwd, run.mapping)


# Integrated, the story's diff carries the main line's changes beside its own: the file list, the tests that existed
# before and the red proof were the stages' to hold, and they held.
@check("files-listed", stages=lambda s: s.lists)
def _files_listed(run):
    check_files_listed(run.result, run.runs, run.story_id, run.stage.name, run.cwd, run.located)
    check_existing_tests(run.result, run.cwd, run.runs, run.story_id, run.body)


@check("test-design", stages=lambda s: s.red)
def _test_design(run):
    check_plan_levels(run.result, run.runs, run.story_id)
    check_invariants(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front, run.mapping)
    check_levels(run.result, run.profile, run.runs, run.story_id, run.front, run.body, run.mapping, run.located)
    check_clauses(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front, run.body, run.mapping,
                  run.located)
    check_titles(run.result, run.profile, run.cwd, run.front, run.body, run.mapping, run.located)


@check("size", stages=lambda s: s.sizes)
def _size(run):
    check_size(run.result, run.runs, run.story_id, run.stage.sizes, len(run.criteria))


@check("red-proof", stages=lambda s: s.lists)
def _red_proof(run):
    # the red proof compares digests, so it belongs here, before any process
    ledger = red_ledger_path(run.runs, run.story_id)
    if run.expected == "green" and ledger and os.path.isfile(ledger):
        check_red_proof(run.result, run.cwd, run.located, read_red_digests(run.runs, run.story_id), run.story_id)


def whole_suites(run):
    """At build and tidy the policy's required test commands run whole anyway: that run is the evidence for the mapped
    tests as well, so those commands are not started a second time."""
    if not run.stage.suite:
        return ()
    return tuple(k for k in test_command_keys(run.profile)
                 if k in set(split_list(run.profile.get("required"))) and run.profile.get(k))


@check("tests", stages=lambda s: s.tested, needs_process=True,
       unrun=lambda run: ["compiles", f"tests-{run.expected}"] + (["suite"] if run.stage.suite else []))
def _tests(run):
    check_compiles(run.result, run.profile, run.cwd)
    run.whole_runs = check_test_state(run.result, run.profile, run.cwd, run.mapping, run.expected, run.located,
                                      run.runs, run.story_id, guard=run.kind in ("journey", "adopt"),
                                      whole_for=whole_suites(run), red_proof=False)
    if run.stage.suite:
        check_required_suites(run.result, run.profile, run.cwd, run.whole_runs)


@check("commands", stages=lambda s: s.commands, needs_process=True,
       unrun=lambda run: [key for key in run.stage.commands if run.profile.get(key)])
def _commands(run):
    check_stage_commands(run.result, run.profile, run.cwd, run.stage.name)


#: What a passing gate does, per stage — the writes a verdict makes.
PASSED = {}


def on_pass(stage):
    if stage not in STAGE or not STAGE[stage].gated:
        raise ValueError(f"on_pass: no gated stage {stage}")

    def register(function):
        PASSED.setdefault(stage, []).append(function)
        return function
    return register


@on_pass("plan")
def _plan_passed(run):
    if is_delivered(run.front):
        # Delivered is delivered: a plan gate run over a delivered story (a check, a re-verification) leaves the
        # story and the marks the delivery rests on as they are.
        run.result.note("story", f"{run.story_id} is delivered — checked, its marks are left as they are")
    else:
        write_mark(run.runs, run.story_id, STORY_DIGEST, story_digest(run.story_path))
        record_tests_baseline(run.cwd, run.runs, run.story_id)


@on_pass("document")
def _document_passed(run):
    result, story_id, story_path = run.result, run.story_id, run.story_path
    if is_delivered(run.front):
        # Delivered is delivered: a document gate run over a delivered story checks it and leaves the story's
        # `delivered:` date as it is.
        result.note("story", f"{story_id} is delivered — checked, its marks are left as they are")
        return
    try:
        if acceptance_applies(run.cwd, run.runs, story_id, run.profile):
            verdict, rid = acceptance_state(run.cwd, story_id, story_path)
            if verdict == "accepted":
                result.ok("acceptance", f"{rid} accepted — the story is delivered")
            elif verdict == "open":
                result.wait("acceptance", f"{rid} waits for a human's look — answer it through "
                                          f"/factory-decisions; the story holds the checkout until then")
                return
            elif verdict == "correction":
                result.fail("acceptance", f"{rid} asked for a correction that is not in the story yet — "
                                          f"write it in (criteria, an `answered:` line naming {rid}); the "
                                          f"story then runs again from plan")
                return
            else:
                asked = ask_acceptance(run.cwd, run.runs, story_id, story_path, run.profile, run.criteria)
                result.wait("acceptance", f"{asked} asks a human to accept the story before it is "
                                          f"delivered — {shown(record_path(story_id, asked, story_path))}, "
                                          f"answered through /factory-decisions")
                return
    except GateError as error:
        result.fail("acceptance", str(error))
        return
    if result.failed:
        return
    if in_worktree():
        # In its worktree a story is delivered when its code is on the main line: the integrate step merges it,
        # holds it to the gate once more, and the integrate gate writes the delivery.
        result.ok("integrate", f"every check passed — {story_id} is delivered once its worktree is integrated "
                               f"into the main checkout (the runner's integrate step)")
        return
    # The one write into a story the gate makes: delivered is its verdict, kept where the story is.
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_story_fields(story_path, status="delivered", delivered=stamp)
    result.ok("delivered", f"{shown(story_path)} carries `status: delivered`, `delivered: {stamp}`")
    # The judge's confirmed defects that did not block: kept beside the story, not in the run folder alone.
    added, open_now = record_findings(story_path, story_id, run.front, run.runs)
    if added or open_now:
        result.ok("findings", f"{added} confirmed finding(s) kept in {shown(findings_path(story_path))} — "
                              f"{open_now} open there")


@on_pass("adopt")
def _adopt_passed(run):
    if is_delivered(run.front):
        return
    if in_worktree():
        run.result.ok("integrate", f"every check passed — {run.story_id} is adopted once its tests are integrated "
                                   f"into the main checkout (the runner's integrate step)")
        return
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_story_fields(run.story_path, delivered=stamp)      # `status: adopted` stays: adopted, never built
    run.result.ok("delivered", f"{shown(run.story_path)} carries `delivered: {stamp}` — adopted")


@on_pass("integrate")
def _integrate_passed(run):
    integrate_into_home(run.result, run.cwd, run.story_path, run.story_id, run.front, run.runs)


def main(argv):
    # `--brief` is the gate's own beside `--stage` (a stage's compact report); alone it is the status's, moved.
    moved = MOVED_TO_CLI - ({"--brief"} if "--stage" in argv else set())
    if any(token.split("=", 1)[0] in moved for token in argv):
        return hand_over_to_cli(argv)
    parser = argparse.ArgumentParser(add_help=True, description="story gate")
    parser.add_argument(
        "--version", action="version",
        version=f"story-gate {VERSION} (file contract {CONTRACT})",
    )
    parser.add_argument("--story")
    parser.add_argument(
        "--stage",
        choices=tuple(s.name for s in STAGES if s.gated),
    )
    parser.add_argument("--change", action="store_true",
                        help="run the profile's checks outside a story and exit")
    parser.add_argument("--staged", action="store_true",
                        help="with --change: check the Git index, refuse when the working tree differs")
    parser.add_argument("--checks", help="with --change: only these checks (compile test architecture format)")
    parser.add_argument("--record-suites", action="store_true",
                        help="the runner's gates: record every passing suite run in the evidence folder's suites.tsv, signed "
                             "with FACTORY_SUITES_KEY, and reuse the runner's own record on an unchanged tree")
    parser.add_argument("--parity", metavar="CONFIG",
                        help="check every implementation's reports against a scenario contract and exit")
    parser.add_argument("--check-contract", action="store_true",
                        help="check the profile's contract and model keys alone (the runner, before its first stage)")
    parser.add_argument("--record-base", action="store_true",
                        help="with --story: record the tree the story's diff is taken against (the first stage)")
    parser.add_argument("--owned", nargs="+", metavar="start|end WINDOW [EXIT]",
                        help="with --story: a stage window's start and end — the person's parts recorded and compared, "
                             "the hand-overs it wrote journaled; EXIT is the window's tool exit (0 by default)")
    parser.add_argument("--record-changes", metavar="STAGE",
                        help="with --story: write changed-<stage>.txt, changed.txt and story.diff from the snapshots")
    parser.add_argument("--project", action="store_true",
                        help="check the project description — product and technical — alone, and exit")
    parser.add_argument("--check-discovery", metavar="TOPIC",
                        help="check the discovery report of one topic (project/discovery/<topic>/) and exit")
    parser.add_argument("--check-backlog", action="store_true",
                        help="the plan gate's backlog checks over every story that is not done (or --story), "
                             "writing nothing, and exit")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`, else project/epics)")
    parser.add_argument("--runs", help="the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)")
    parser.add_argument("--profile", help=f"the stack profile (default: {PROFILE_FILE} at the project root)")
    parser.add_argument("--root", default=".", help="the project's root directory")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--brief", action="store_true",
                        help="with --story --stage: the checks that passed as one line, the rest verbatim "
                             "(for a stage that runs its own gate and reads the report)")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.root)
    os.chdir(cwd)
    # Every place once: the flag, else the profile's key, else the default. None reads an older layout —
    # the gate names the move instead.
    set_places(read_profile(resolve_profile(args.profile, cwd)), epics=args.epics, runs=args.runs)
    args.epics, args.runs = place("epics"), place("runs")
    if args.check_backlog:
        return check_backlog(cwd, args.epics, read_profile(resolve_profile(args.profile, cwd)), args.story)
    if args.check_contract:
        result = Result()
        profile = read_profile(resolve_profile(args.profile, cwd))
        check_contract(result, profile)
        check_models(result, profile)
        for state, check, message in result.entries:
            if state != "pass":
                print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else 0
    if args.owned:
        if not args.story:
            parser.error("--owned needs --story")
        if args.owned[0] == "start":
            record_owned(args.runs, args.story)
            return 0
        if len(args.owned) < 2:
            parser.error("--owned takes start|end and the window's name")
        return owned_end(args.runs, args.story, args.owned[1], args.owned[2] if len(args.owned) > 2 else "0")
    if args.record_base or args.record_changes:
        if not args.story:
            parser.error("--record-base/--record-changes need --story")
        if args.record_base:
            record_base(cwd, args.runs, args.story)
        if args.record_changes:
            record_changes(cwd, args.runs, args.story, args.record_changes)
        return 0
    if args.check_discovery:
        result = Result()
        try:
            check_discovery(result, cwd, read_profile(resolve_profile(args.profile, cwd)), args.check_discovery)
        except GateError as error:
            result.fail("discovery", str(error))
        for state, check, message in result.entries:
            print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else 0
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
    if args.change or args.parity:
        result, label = Result(), "change" if args.change else "parity"
        try:
            if args.change:
                profile = read_profile(resolve_profile(args.profile, cwd))
                if layout_hint(cwd, profile):
                    result.fail("layout", layout_hint(cwd, profile))
                check_contract(result, profile)
                change_check(result, cwd, profile, args.staged, args.checks)
            else:
                parity(result, args.parity)
        except GateError as error:
            result.fail("gate", str(error))
        return result.report(label, label, args.json)
    if not args.story or not args.stage:
        parser.error("--story and --stage are required (or --change, --parity, --check-backlog, --project; "
                     "status, schedule, usage and the inbox are factory-cli.py's)")
    result = Result()
    hint = layout_hint(cwd, read_profile(resolve_profile(args.profile, cwd)))
    if hint:
        # Not a note: a profile or a story the gate does not read would leave every check skipped and named,
        # and a green run that covers nothing.
        result.fail("layout", hint)
    story_path = story_id = None
    try:
        story_path = find_story(args.epics, args.story)
        front, body = read_front_matter(story_path)
        story_id = str(front.get("id") or os.path.basename(story_folder(story_path)))
        observe_writes(args.runs, story_id)
        criteria = criteria_of(story_path, body)
        run = GateRun(result=result, args=args, cwd=cwd, runs=args.runs, stage=STAGE[args.stage], story_id=story_id,
                      story_path=story_path, front=front, body=body, criteria=criteria,
                      profile=read_profile(resolve_profile(args.profile, cwd)))
        run_checks(run)
    except GateError as error:
        result.fail("gate", str(error))
        return journal_gate(result, args, story_id, story_path, result.report(args.story, args.stage, args.json,
                                                                              args.brief))
    if not result.failed:
        for finish in PASSED.get(args.stage, ()):
            finish(run)
    return journal_gate(result, args, story_id, story_path, result.report(story_id, args.stage, args.json, args.brief))


CONFLICT_MARKER = re.compile(r"^(<{7} |={7}$|>{7} )", re.M)


def integration_target(runs, story_id):
    """The branch of the main checkout the story integrates into — recorded when its worktree was made."""
    path = os.path.join(evidence_dir(runs, story_id), "target")
    return read_text(path).strip() if os.path.isfile(path) else ""


def check_integrated(result, cwd, runs, story_id):
    """The story's branch carries the main line and nothing half-merged: no unmerged path, no conflict marker in
    a file the story's commit changes, and its commit sits on the target's tip — a target that moved since is
    integrated again (`moved`), not refused."""
    if not in_worktree(cwd):
        result.fail("integrate", f"the integrate gate runs in the story's worktree, with {HOME_VARIABLE} naming the "
                                 f"main checkout — the runner's integrate step starts it")
        return
    target = integration_target(runs, story_id)
    if not target:
        result.fail("integrate", f"no target recorded for {story_id} (<evidence>/<story>/target) — the worktree was not made "
                                 f"by the runner")
        return
    code, unmerged = git(cwd, "diff", "--name-only", "--diff-filter=U")
    if unmerged.strip():
        result.fail("conflicts", "unmerged: " + ", ".join(unmerged.split()) + " — the merge is not finished")
        return
    code, changed = git(cwd, "diff", "--name-only", f"{target}...HEAD")
    marked = []
    for rel in changed.split("\n") if code == 0 else []:
        full = os.path.join(cwd, rel.strip())
        if rel.strip() and os.path.isfile(full):
            with contextlib.suppress(OSError, UnicodeDecodeError):
                with open(full, encoding="utf-8") as handle:
                    if CONFLICT_MARKER.search(handle.read()):
                        marked.append(rel.strip())
    if marked:
        result.fail("conflicts", "a conflict marker is left in " + ", ".join(marked))
    else:
        result.ok("conflicts", "no unmerged path, no conflict marker in the story's files")
    tip = git(cwd, "rev-parse", target)[1].strip()
    parent = git(cwd, "rev-parse", "HEAD~1")[1].strip() if git(cwd, "rev-parse", "HEAD")[1].strip() != tip else tip
    if tip and parent and tip != parent:
        result.fail("moved", f"{target} moved on since the story was merged with it — the integrate step merges again")


def integrate_into_home(result, cwd, story_path, story_id, front, runs):
    """Every check holds on the integrated tree: the main checkout takes the story's commit — a fast-forward of
    its branch, nothing else — and the story is delivered. A main checkout on another branch, or with changes
    of its own in a file the commit touches, does not take it: refused (`checkout`), the person decides."""
    home, target = factory_home(), integration_target(runs, story_id)
    on = git(home, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip()
    if on != target:
        result.fail("checkout", f"the main checkout is on {on or 'a detached HEAD'}, the story integrates into "
                                f"{target} — switch back, then `factory.sh run --story {story_id} --from integrate`")
        return
    head = git(cwd, "rev-parse", "HEAD")[1].strip()
    done = subprocess.run(["git", "merge", "--ff-only", "--quiet", head], cwd=home, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        result.fail("checkout", f"the main checkout could not take the story's commit: "
                                f"{(done.stderr or done.stdout).strip().splitlines()[0] if (done.stderr or done.stdout).strip() else 'git refused'}"
                                f" — commit or stash what is in the way there, then "
                                f"`factory.sh run --story {story_id} --from integrate`")
        return
    result.ok("integrated", f"{target} took the story's commit {head[:12]}")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if story_kind(front) == "adopt":
        write_story_fields(story_path, delivered=stamp)      # `status: adopted` stays: adopted, never built
    else:
        write_story_fields(story_path, status="delivered", delivered=stamp)
    result.ok("delivered", f"{shown(story_path)} carries `delivered: {stamp}`")
    added, open_now = record_findings(story_path, story_id, front, runs)
    if added or open_now:
        result.ok("findings", f"{added} confirmed finding(s) kept in {shown(findings_path(story_path))} — "
                              f"{open_now} open there")


def journal_gate(result, args, story_id, story_path, code):
    """Every gate run over a story is an event: `gate <stage> exit=<code> fail=<checks> by=<who>` — the runner's
    (`by=runner`, the one that signs suites), a stage's own under a runner (`by=<stage>`), a session's (`by=session`).
    The plan gate's refusal carries the backlog's digest, so a repair is seen without a clock."""
    if not story_id:
        return code
    failed = sorted({check for state, check, _ in result.entries if state == "fail"})
    by = "runner" if args.record_suites else (os.environ.get("FACTORY_STAGE") or "stage") \
        if os.environ.get("FACTORY_WORKER") else "session"
    fields = [f"exit={code}"] + ([f"fail={','.join(failed)}"] if failed else []) + [f"by={by}"]
    if args.stage == "plan" and code == 1 and story_path:
        fields.append(f"backlog={backlog_digest(story_path)}")
    with contextlib.suppress(OSError):
        journal_append(args.runs, story_id, "gate", args.stage, *fields)
    return code
