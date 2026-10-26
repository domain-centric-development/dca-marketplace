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
    --epics <dir>       where the epics and stories are (default: the profile's `epics:`, else product/epics)
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
           evidence: a runner that matched no test at all exits 0 exactly like a passing one. Every file
           the plan's `## Files` says `new` is there, every one it says `removed` is gone (contract 22)
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

Where things are — one owner per place: `product/` is the people's (the description, the epics with
their stories, each story a folder with its decisions), `.agents/factory/` is the installed pipeline,
the profile at the root is the person's, and `.dca-factory/` is the run's protocol (hand-overs, marks,
the journal), disposable at any time: what is delivered stands in the story itself (`status:
delivered`, written by the gate alone), so deleting the run folder loses history, never state.

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import contextlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from .contract import (
    CONTRACT, CRITERION, GateError, layout_hint, order_for, SELECTOR, STAGE, STAGE_CHECKS, STAGES, VERSION)
from .delivery.adapter.outgoing.files.findings_files import (
    append_finding_rows, confirmed_defects, findings_cells, findings_path, open_findings,
    PLAIN_COLUMN, project_findings_head, project_findings_path, record_findings)
from .delivery.adapter.outgoing.files.story_layout import (
    duplicate_ids, file_digest, find_story, is_delivered, story_digest,
    story_files, story_folder, story_id_of, story_kind)
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, evidence_dir, evidence_rel, factory_home, FLAKY_FINDINGS, in_worktree,
    JOURNAL, location, place, PLACES, PROFILE_FILE, read_profile,
    resolve_profile, set_places, shown)
from .delivery.adapter.outgoing.git.repository import git, git_identity
from .delivery.adapter.outgoing.files.decision_record_files import (
    answered_decisions, decisions_store, record_path)
from .delivery.domain.model.correction import REASON_CODES
from .delivery.application.description.check_description import CheckDescriptionCommand
from .discovery.api import check_report
from .infrastructure.description import check_description
from .sharedkernel.adapter.outgoing.markdown.sections import section_of
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .delivery.adapter.outgoing.build.test_reports import (
    display_name_of, unescape_literal)
from .spec.api import (
    derived, merge, merge_context, lint_context, read_delta, read_spec, render_spec, scenarios_path, story_entries)
from .delivery.adapter.outgoing.claims.remote_claims import claim_config_here, PUBLISHED
from .delivery.adapter.outgoing.files.story_record import INVARIANT_BREAKS
from .delivery.adapter.outgoing.files.signals import journal_signal, latest_signal, plan_left_open, record_judge_signal
from .delivery.adapter.outgoing.files.snapshots import (
    git_tree, record_base, record_changes)
from .delivery.adapter.outgoing.files.owned_files import owned_end, run_owned
from .delivery.adapter.outgoing.files.run_marks import (
    backlog_digest, current_stage_files, last_ended, step_open,
    STORY_DIGEST, verdict_in, write_mark)
from .delivery.adapter.outgoing.files.owned_files import observe_writes, record_owned
from .delivery.adapter.outgoing.files.journal_files import flaky_tests, journal_append, journal_events
from .delivery.adapter.outgoing.files.decision_record_files import (
    ACCEPTANCE_KIND, acceptance_mode, acceptance_records, acceptance_state)
from .delivery.application.shared.front import is_acceptance
from .delivery.domain.model.verdict import FindingState
from .delivery.domain.service.backlog_checks import BacklogChecks
from .delivery.domain.service.profile_checks import ProfileChecks
from .delivery.domain.service.story_checks import StoryChecks
from .delivery.domain.service.decision_checks import Applying, DecisionChecks
from .delivery.domain.model.stage import StageName
from .delivery.domain.model.stage_story import (
    CommandKey, Count, MappedTest, Place, Presence, ScenarioKey, Selector, TestTable, TitleCheck, TitleFound)
from .delivery.domain.model.story_state import Detail
from .delivery.domain.service.design_checks import DesignChecks
from .delivery.domain.service.kept_checks import KeptChecks
from .delivery.domain.service.spec_checks import SpecChecks
from .delivery.domain.service.delivery_checks import DeliveryChecks
from .delivery.domain.service.integration_checks import IntegrationChecks
from .delivery.domain.service.test_verdicts import BreakProof, TestVerdicts
from .delivery.domain.service.break_checks import BreakChecks, BreakOutcome, BreakResult
from .delivery.domain.model.verdict import Finding
from .delivery.application.delivery.stage_checks import table_tests  # registers the checks over the evidence alone
from .delivery.application.delivery.check_stage import (
    check, on_pass, run_checks, run_passed, StageRun, Verdict)
from .delivery.domain.model.stage import StoryKind, TESTED_KINDS as TESTED, Trait
from .delivery.domain.service.acceptance_rules import AcceptanceMode, AcceptanceRules
from .delivery.domain.model.story_state import Acceptance, AcceptanceVerdict
from .delivery.domain.model.decision_record import RecordId
from .delivery.domain.model.moment import Moment
from .delivery.domain.model.story import StoryId
from .delivery.adapter.outgoing.files.story_files import StoryFiles
from .delivery.domain.service.change_checks import CHANGE_CHECKS, ChangeChecks
from .delivery.domain.model.stage_story import CommandRun
from .delivery.adapter.outgoing.git.change import parity_facts, snapshot
from .delivery.domain.service.suite_checks import red as red_finding, SuiteChecks
from .delivery.domain.model.verdict import CheckName, Said
from .delivery.adapter.outgoing.build.suite_runs import command_run, suite_commands, suite_run
from .delivery.domain.model.stage_story import Expectation
from .delivery.adapter.outgoing.build.test_runs import red_ledger, run_tests
from .delivery.domain.service.test_checks import HANDOVER_BUDGET, TestChecks  # noqa: F401 — HANDOVER_BUDGET: read by the runner
from .delivery.adapter.outgoing.files.test_files import locate_tests
from .delivery.adapter.outgoing.files.stage_evidence_files import DecisionStampFiles, StageEvidenceFiles, stage_story, closed_rows, closes_of, happy_paths, split_list
from .delivery.adapter.outgoing.files.test_files import read_mapping
from .delivery.adapter.outgoing.files.design_files import STEP, read_invariant_rows
from .delivery.adapter.outgoing.files.kept_files import RED_TREE, read_red_digests, red_ledger_path, red_tree, tidy_moves, unproven_tests
from .delivery.adapter.outgoing.files.kept_files import TESTS_BASELINE
from .delivery.adapter.outgoing.spec.story_spec_files import moved_tests, story_spec
from .delivery.adapter.outgoing.files.delivery_files import TEST_DIR, TEST_FILE
from .delivery.adapter.outgoing.git.integration import integration_target
from .delivery.adapter.outgoing.build import commands
from .delivery.adapter.outgoing.build.commands import MISSING_TOOLS, command_for, open_suites_record, run, tail, test_command_keys
from .delivery.adapter.outgoing.build.suite_runs import SuiteOwner, test_files
from .delivery.adapter.outgoing.build.breaks import apply_break, break_copy, break_patch, break_path, characterization_tests, qualify_selector
from .delivery.adapter.outgoing.git.change import backlog_paths


def story_ids(epics):
    """Every story id under the epics, in the order of the files — front matter first, else the file name."""
    return [story_id_of(path) for path in story_files(epics)]


SCENARIO_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def criteria_of(story_path, body, front=None):
    """Acceptance criteria as (key, text) pairs, read from the `## Acceptance criteria` section — none for a task
    (`front` given), which has no criterion.

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
        if line[:1].isspace() and not stripped.startswith(("-", "#")):
            # a Markdown continuation line: the step or line criterion above it goes on
            if scenario is not None and scenario[1]:
                word, text = scenario[1][-1]
                scenario[1][-1] = (word, f"{text} {stripped}")
                continue
            if scenario is None and found:
                key, text = found[-1]
                found[-1] = (key, f"{text} {stripped}")
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
    if not found and story_kind(front or {}) == "task":
        return []
    if not found:
        raise GateError(
            f"{story_path}: no acceptance criteria — add a `## Acceptance criteria` "
            f"section with one `- <key>: <criterion>` line or one `#### <key>` scenario per criterion"
        )
    return found


def contract_of(profile):
    declared = str(profile.get("contract", "")).strip()
    return int(declared) if declared.isdigit() else CONTRACT


def check_task_suites(result, profile, cwd, owner=None):
    """At a task's build and tidy gates: every test command the profile declares, run whole — nothing a test was
    written for, so everything the stories before delivered has to hold."""
    found = SuiteChecks.task(suite_commands(profile))
    take(result, found)
    if found:
        return
    seen = set()
    for key in [key for key in test_command_keys(profile) if profile.get(key)]:
        if profile[key] in seen:
            continue
        seen.add(profile[key])
        before = len(result.entries)
        run_test_command(result, cwd, profile, key, profile[key], True, True, owner=owner)
        result.entries[before:] = [(state, "suite" if check != "flaky" else check, message)
                                   for state, check, message in result.entries[before:]]


def close_findings(result, front):
    """At a task's delivery: the rows it names under `closes:` set to `done` in their findings.md."""
    closed = []
    for row_id in closes_of(front):
        path, row = closed_rows(row_id)
        if not path or row[6] != "open":
            continue
        lines = read_text(path).splitlines()
        for index, line in enumerate(lines):
            cells = findings_cells(line)
            if cells and cells[0] == row[0]:
                cells[-1] = "done"
                lines[index] = "| " + " | ".join(cells) + " |"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        result.written.append(path)
        closed.append(row_id)
    if closed:
        result.ok("findings", f"closed {', '.join(closed)} — set to done in their findings.md")


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


def scenarios_of(body):
    """The criteria as a person reads them (WP-146), in the story's order: [{key, title, rule, happy, steps, text}] —
    `steps` the scenario's `[{word, text}]` (Given / When / Then / And / But), `text` the line form's criterion, `rule`
    the `### Rule:` it stands under, `happy` its happy-path mark. A reader for the views: it refuses nothing —
    `criteria_of` is the check."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    titles, happy = scenario_titles(body), set(happy_paths(body))
    found, rule, current = [], "", None
    for line in section.splitlines():
        stripped = line.strip()
        if line.startswith("### "):
            heading = line[4:].strip()
            rule, current = (heading[5:].strip() if heading.lower().startswith("rule:") else heading), None
            continue
        heading = re.match(r"^####\s+([a-z0-9][a-z0-9-]*)", stripped)
        criterion = CRITERION.match(stripped)
        step = STEP.match(stripped)
        if heading:
            key = heading.group(1)
            current = dict(key=key, title=titles.get(key, key), rule=rule, happy=key in happy, steps=[], text="")
            found.append(current)
        elif step and current is not None:
            current["steps"].append(dict(word=step.group(1), text=step.group(2).strip()))
        elif stripped and line[:1].isspace() and found and (found[-1]["steps"] or found[-1]["text"]):
            # a Markdown continuation line: the step or line criterion above it goes on
            last = found[-1]["steps"][-1] if found[-1]["steps"] else found[-1]
            last["text"] = f"{last['text']} {stripped}"
        elif criterion:
            key = criterion.group(1)
            found.append(dict(key=key, title=titles.get(key, key), rule=rule, happy=key in happy, steps=[],
                              text=criterion.group(2).strip()))
            current = None
    return found


def carries_title(path, method, title):
    """The test is reported under the title: its display name where the declaration gives one, else a string
    literal that is the title — never the words somewhere in a comment or another test."""
    display = display_name_of(path, method)
    if display is not None:
        return display == title
    text = read_text(path) if os.path.isfile(path) else ""
    return any(unescape_literal(m.group(2)) == title
               for m in re.finditer(r"""(["'`])((?:\\.|(?!\1).)*)\1""", text))


def check_clauses(result, profile, cwd, runs, story_id, front, body, mapping, located):
    """Every expectation of every scenario names the line that asserts it (`DesignChecks.clauses`) — over a story
    read from its body alone."""
    story = stage_story(story_id, "", front, body, ())
    evidence = StageEvidenceFiles(cwd, runs, place("epics"), profile)
    tests = tuple(MappedTest(ScenarioKey(key), Selector(selector),
                             Place((located or {})[selector]) if (located or {}).get(selector) else None, None, None)
                  for key, selectors in (mapping or {}).items() for selector in selectors)
    take(result, DesignChecks.clauses(story, ProfileChecks.contract_number(evidence), tests, evidence))


def check_invariants(result, profile, cwd, runs, story_id, front, mapping):
    """Every rule of a domain type the plan names has a unit test of its own (`DesignChecks.invariants`) — for the
    adopt gate, which reads the story without a run of its own."""
    story = stage_story(story_id, "", front, "", ())
    evidence = StageEvidenceFiles(cwd, runs, place("epics"), profile)
    tests = tuple(MappedTest(ScenarioKey(key), Selector(selector), None, None, None)
                  for key, selectors in (mapping or {}).items() for selector in selectors)
    take(result, DesignChecks.invariants(story, ProfileChecks.contract_number(evidence), tests, evidence))


def check_adopt(result, profile, cwd, runs, story_id, front, criteria):
    """The adopt gate: an adopted story is delivered when every scenario maps to a test that exists and
    is green, a fresh judge passed it, and every test the adoption wrote itself turns red under its
    break — a minimal change to the production code, applied to a scratch copy, never to the tree."""
    refused = BreakChecks.adopted(stage_story(story_id, "", front, "", ()))
    take(result, refused)
    if refused:
        return
    mapping = check_mapping(result, runs, story_id, criteria)
    located = check_exists(result, cwd, mapping)
    check_compiles(result, profile, cwd)
    check_invariants(result, profile, cwd, runs, story_id, front, mapping)
    # every rule's unit test is green beside the scenarios' tests: an adoption proves what holds, the rules included
    tests_path = os.path.join(runs, story_id, "tests.md")
    rows = read_invariant_rows(read_text(tests_path)) if os.path.isfile(tests_path) else None
    rules = {f"{element} rule {', '.join(map(str, numbers))}": [selector] for element, numbers, selector in rows or []
             if selector and SELECTOR.match(selector) and selector not in {s for sels in mapping.values() for s in sels}}
    if rules and contract_of(profile) >= 24:
        located = dict(located or {}, **(check_exists(Result(), cwd, rules) or {}))
        mapping = dict(mapping, **rules)
    check_test_state(result, profile, cwd, mapping, "green", located, runs, story_id, guard=True)
    judge = read_text(os.path.join(runs, story_id, "judge.md")) if os.path.isfile(os.path.join(runs, story_id, "judge.md")) else ""
    take(result, (BreakChecks.adopt_judged(Detail(verdict_in(judge) or "")),))
    everything = str(profile.get("adopt.breakProof", "")).strip().lower() == "all"
    by_selector = {sel: key for key, sels in mapping.items() for sel in sels}
    written = [qualify_selector(sel, by_selector, cwd) for sel in characterization_tests(runs, story_id)]
    wanted = sorted(by_selector) if everything else written
    extra = {sel for sel in wanted if sel not in located}
    if extra:
        located = dict(located, **check_exists(Result(), cwd, {"outside the table": sorted(extra)}))
    if wanted:
        with break_copy(cwd) as copied:
            for selector in wanted:
                check_break(result, profile, cwd, runs, story_id, selector,
                            by_selector.get(selector, "outside the table"), located, copied)
    if not wanted:
        take(result, (BreakChecks.nothing_written(),))


def break_verdict(probe):
    """The outcome of a break's run, from the `tests-red` entries of its result (`BreakChecks.verdict`)."""
    return BreakChecks.verdict(findings_of(probe, "tests-red"))


def findings_of(probe, check, about=None):
    """A result's entries of one check as findings — of one test, where `about` names it."""
    return tuple(Finding(FindingState(state), CheckName(c), Said(m)) for state, c, m in probe.entries
                 if c == check and (about is None or m.startswith(about + " ") or m.startswith(about + ":")))


def run_break(profile, copy, scratch, patch, selector, key, located):
    """One break on a scratch copy the caller made: applied, the one test run, taken back — so the next break on the
    same copy builds on what this one compiled."""
    code, said = apply_break(copy, scratch, patch)
    if code != 0:
        return BreakResult(BreakOutcome.UNAPPLIED, Detail(said[:200]))
    try:
        probe = Result()
        check_test_state(probe, profile, copy, {key: [selector]}, "red",
                         {selector: located.get(selector)} if located.get(selector) else {})
        return break_verdict(probe)
    finally:
        apply_break(copy, scratch, patch, reverse=True)


def check_break(result, profile, cwd, runs, story_id, selector, key, located, copied=None):
    """A test green without ever being seen red, held to its break (`BreakChecks.proof`)."""
    patch = break_patch(runs, story_id, selector)
    outcome = None
    if patch:
        with (contextlib.nullcontext(copied) if copied else break_copy(cwd)) as (copy, scratch):
            outcome = run_break(profile, copy, scratch, patch, selector, key, located)
    take(result, (BreakChecks.proof(Selector(selector), Detail(key), outcome,
                                    Place(os.path.relpath(break_path(runs, story_id, selector), cwd))),))


CORRECTION_CODE = re.compile(r"^\s*correction:\s*([a-z-]+)\s*:", re.I)


def correction_code(answer):
    """The reason code of an acceptance correction's answer, `uncoded` for one that names none (or none known), None
    for an answer that is no correction."""
    text = str(answer or "").strip()
    if not text.lower().startswith("correction:"):
        return None
    match = CORRECTION_CODE.match(text)
    return match.group(1).lower() if match and match.group(1).lower() in REASON_CODES else "uncoded"


def story_signals(runs, story_id, records, body):
    """WP-148 B/C: the raw facts of one story the bench aggregates — questions the stages asked and how many a person
    answered, the story's assumptions open and answered, what the plan left open, each named rule's verdict at the
    test gate, the judge's confirmed findings by perspective and domain code, the acceptance corrections by reason
    code. Counted, never rated. What a gate decided is read from the journal alone (WP-150): a fact no gate recorded
    is None — "not recorded", never 0."""
    questions = [(front, state) for _p, front, _b, state, _a in records if not is_acceptance(front)]
    lines = [l.strip()[1:].strip().lower() for l in section_of(body, "assumptions") or [] if l.strip().startswith(("-", "*"))]
    events = journal_events(runs, story_id)
    plan = latest_signal(events, "plan")
    rules_group = latest_signal(events, "rules", "rule")
    rules = {}
    for _sel, fields in rules_group[1] if rules_group else []:
        verdict = fields.get("verdict", "unchecked")
        rules[verdict] = rules.get(verdict, 0) + len([n for n in fields.get("rules", "").split(",") if n])
    judge = latest_signal(events, "judge", "finding")
    findings, domain = {}, {}
    for perspective, fields in judge[1] if judge else []:
        findings[perspective] = findings.get(perspective, 0) + 1
        if fields.get("code"):
            domain[fields["code"]] = domain.get(fields["code"], 0) + 1
    corrections = {}
    for _p, front, _b, state, answer in records:
        code = correction_code(answer.get("answer")) if is_acceptance(front) and state in ("answered", "applied") else None
        if code:
            corrections[code] = corrections.get(code, 0) + 1
    return dict(asked=len(questions), answered=sum(1 for _f, st in questions if st in ("answered", "applied")),
                assumptions_open=sum(1 for l in lines if l.startswith("open:")),
                assumptions_answered=sum(1 for l in lines if l.startswith("answered:")),
                plan_open=int(plan[0].get("open", 0)) if plan else None,
                rules=rules if rules_group else None,
                findings=findings if judge else None, domain=domain if judge else None,
                corrections=corrections)


def check_invariant_breaks(result, profile, cwd, runs, story_id, mapping):
    """WP-148 A: every rule the plan names is shown to be guarded by its unit test. Its test seen red before the
    build proves it as a criterion's red run does; one green already — the rule exists — needs its break, one change
    to the production code that turns it red. All breaks of the gate run on one scratch copy, each running its one
    test, so the second compiles on the first. A survived or missing break is refused."""
    tests_path = os.path.join(runs, story_id, "tests.md")
    rows = read_invariant_rows(read_text(tests_path)) if os.path.isfile(tests_path) else None
    criterion = {sel for sels in (mapping or {}).values() for sel in sels}
    rules = {}
    for element, numbers, selector in rows or []:
        if selector and SELECTOR.match(selector) and selector not in criterion:
            rules.setdefault(selector, []).append((element, numbers))
    if not rules:
        return
    keys = {sel: "; ".join(f"{e} rule {', '.join(map(str, n))}" for e, n in owners) for sel, owners in rules.items()}
    located = check_exists(Result(), cwd, {keys[sel]: [sel] for sel in rules}) or {}
    probe = Result()
    check_test_state(probe, profile, cwd, {keys[sel]: [sel] for sel in sorted(rules)}, "red", located)
    before = {sel: BreakChecks.verdict(findings_of(probe, "tests-red", sel)) for sel in rules}
    proofs = {}
    green = [sel for sel in sorted(rules) if before[sel].outcome is BreakOutcome.GREEN]
    with (break_copy(cwd) if green else contextlib.nullcontext((None, None))) as copied:
        for sel in sorted(rules):
            under = None
            if sel in green:
                patch = break_patch(runs, story_id, sel)
                under = run_break(profile, *copied, patch, sel, keys[sel], located) if patch else None
            proofs[sel] = BreakChecks.rule_proof(before[sel], under)
    verdicts = {sel: proof.value for sel, proof in proofs.items()}
    write_mark(runs, story_id, INVARIANT_BREAKS, "\n".join(
        f"{e}\t{','.join(map(str, n))}\t{sel}\t{verdicts[sel]}" for sel, owners in sorted(rules.items())
        for e, n in owners))
    journal_signal(runs, story_id, "rules", [("rule", sel, dict(element=e, rules=",".join(map(str, n)),
                                                                verdict=verdicts[sel]))
                                             for sel, owners in sorted(rules.items()) for e, n in owners],
                   named=sum(len(n) for owners in rules.values() for _e, n in owners))
    for sel in sorted(rules):
        said = "; ".join(m for _st, _c, m in probe.entries if sel in m)
        take(result, (BreakChecks.invariant(Selector(sel), Detail(keys[sel]), proofs[sel],
                                            Place(os.path.relpath(break_path(runs, story_id, sel), cwd)),
                                            Detail(said)),))


def take(result, findings):
    """A domain check's findings into the result, as the gate reports them."""
    result.take(findings)


def gate_run(**fields):
    """What one gate run over a story knows: the fields `main` read, and the story, its evidence and its contract
    from them."""
    run = StageRun(**fields)
    run.kind = story_kind(run.front)
    run.evidence = StageEvidenceFiles(run.cwd, run.runs, run.args.epics, run.profile)
    run.story = stage_story(run.story_id, run.story_path, run.front, run.body, run.criteria)
    run.contract = ProfileChecks.contract_number(run.evidence)
    # a journey is a guard over what is delivered: green at its test gate, the inverse of a story
    run.expected = "red" if run.stage.red and run.kind == "story" else "green"
    return run


def check_contract(result, profile):
    """The profile's contract and its unknown keys (`ProfileChecks.contract`)."""
    take(result, ProfileChecks.contract(StageEvidenceFiles(".", "", "", profile)))


def check_models(result, profile):
    """The profile's model keys, each bound to a tool (`ProfileChecks.models`)."""
    take(result, ProfileChecks.models(StageEvidenceFiles(".", "", "", profile)))


#: Where the method keeps the project's conventions; `verify_command:` there is the architecture command the
#: profile's `architecture:` was copied from at setup. Two files, two owners — the method's and the factory's —
#: and nothing merges them, so the pair is compared and a difference is named.
def check_project(result, cwd, profile):
    """The two mandatory parts of the project description — the description feature's check, said as the gate
    says its checks."""
    checked = check_description(cwd, profile).execute(CheckDescriptionCommand())
    for verdict in checked.verdicts:
        getattr(result, verdict.state)(verdict.part, verdict.said)
    return checked.complete


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
            story = stage_story(label, path, front, body, criteria_of(path, body, front))
            evidence = StageEvidenceFiles(cwd, "", epics, profile)
            contract = ProfileChecks.contract_number(evidence)
            take(result, StoryChecks.context(story))
            if story.context.value:
                take(result, BacklogChecks.context_map(story, evidence))
            take(result, BacklogChecks.epic(story, evidence))
            take(result, BacklogChecks.outcome(story, contract, evidence))
            take(result, StoryChecks.happy_path(story, contract, evidence))
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


def check_mapping(result, runs, story_id, criteria):
    """The tests table names a test for every criterion and no other (`TestChecks.mapped`); the mapping, or {}."""
    try:
        path, mapping = read_mapping(runs, story_id)
    except GateError as error:
        result.fail("tests-mapped", str(error))
        return {}
    table = TestTable(Place(path), tuple(ScenarioKey(key) for key in mapping),
                      Count(sum(len(selectors) for selectors in mapping.values())))
    take(result, TestChecks.mapped(tuple(ScenarioKey(key) for key, _text in criteria), table))
    return mapping


def check_exists(result, cwd, mapping):
    """Each mapped test is there (`TestChecks.exist`): {selector: file} for the ones found."""
    if not mapping:
        return None
    located, looked = locate_tests(cwd, mapping)
    take(result, TestChecks.exist(looked))
    return located


def mapped_tests(run):
    """The tests table's rows as the test-design checks read them: each test's file, the command that runs it, and an
    end-user test's title check."""
    cached = getattr(run, "tests", None)
    if cached is not None and cached[0] is run.mapping and cached[1] is run.located:
        return cached[2]
    titles = scenario_titles(run.body)
    rows = []
    for key, selectors in (run.mapping or {}).items():
        for selector in selectors:
            path = (run.located or {}).get(selector)
            command = command_for(run.profile, path)[0] if path else None
            title = None
            if path and command in ("e2eTest", "test.journey") and key in titles:
                carries = carries_title(os.path.join(run.cwd, path), selector.split("#", 1)[-1], titles[key])
                title = TitleCheck(Detail(titles[key]), TitleFound.TITLED if carries else TitleFound.UNTITLED)
            rows.append(MappedTest(ScenarioKey(key), Selector(selector), Place(path) if path else None,
                                   CommandKey(command) if command else None, title))
    run.tests = (run.mapping, run.located, tuple(rows))
    return run.tests[2]


def check_compiles(result, profile, cwd):
    """The profile's `compile:` command passes (`SuiteChecks.command`)."""
    command = profile.get("compile")
    take(result, (SuiteChecks.command(COMPILES, command_run(cwd, command)) if command
                  else SuiteChecks.missing(COMPILES, CommandKey("compile")),))


def check_stage_commands(result, profile, cwd, stage):
    """The gate must not *know* its checks, it looks them up. Adding a capability is
    then one line in the profile, not an edit to a stage."""
    for key in STAGE_CHECKS.get(stage, ()):
        command = profile.get(key)
        take(result, (SuiteChecks.command(CheckName(key), command_run(cwd, command)) if command
                      else SuiteChecks.missing(CheckName(key), CommandKey(key)),))


def check_test_state(result, profile, cwd, mapping, expected, located=None, runs=None, story=None, guard=False,
                     whole_for=(), red_proof=True):
    """expected 'red': every mapped test must fail. 'green': all must pass (`TestVerdicts`) — the tests run first
    (`run_tests`), their outcomes judged against the red ledger. A break proof the judgement asks for is run here;
    a test it proves counts as red, one it does not keeps its earlier proof. Returns the commands run whole —
    `{command: (key, code, output, ran)}` — so the suite check reads them rather than running them again.
    `red_proof=False` leaves the red proof to a caller that checked it before any process started."""
    located = located or {}
    if (profile.get("e2eTest") or profile.get("test")) and not mapping:
        return {}
    test_run, whole_runs = run_tests(profile, cwd, mapping or {}, located, whole_for)
    ledger = red_ledger(cwd, runs, story, expected == "red", located)
    judged = TestVerdicts.judge(Expectation(expected), Presence.PRESENT if guard else Presence.ABSENT, test_run, ledger)
    now_red, kept = {s.value for s in judged.now_red}, {}
    for item in judged.items:
        if not isinstance(item, BreakProof):
            take(result, (item,))
            continue
        probe = Result()
        check_break(probe, profile, cwd, runs, story, item.selector.value, item.key.value, located)
        result.entries.extend(probe.entries)
        if not probe.failed:
            now_red.add(item.selector.value)
        else:
            # The earlier proof stands for the version it was taken against; losing it would make the next run
            # treat this test as one never seen red, which no break can repair.
            kept[item.selector.value] = read_red_digests(runs, story).get(item.selector.value)
    if test_run.command is Presence.ABSENT:
        return whole_runs
    if expected == "red":
        write_red_ledger(runs, story, now_red, located, cwd, kept)
    elif ledger.present is Presence.PRESENT and red_proof:
        check_red_proof(result, cwd, runs, located, story)
    return whole_runs


def check_red_proof(result, cwd, runs, located, story_id):
    """Every test is the version the test stage saw fail (`KeptChecks.red_proof`) — after a whole run of the tests."""
    tests = tuple(MappedTest(ScenarioKey(""), Selector(selector), Place(path), None, None)
                  for selector, path in (located or {}).items() if path)
    take(result, KeptChecks.red_proof(stage_story(story_id, "", {}, "", ()), StageName(""), tests,
                                      StageEvidenceFiles(cwd, runs, place("epics"), {})))


def stale_red_proof(cwd, runs, story, start=None):
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
    moved = unproven_tests(cwd, check_exists(Result(), cwd, mapping) or {}, digests)
    if not moved or answered_decisions(cwd, story, "test"):
        return []
    if start == "tidy" and red_tree(runs, story) and last_ended(runs, story, tuple(s.name for s in STAGES if s.lists and not s.red)) == "tidy":
        # A tidy that runs again moved the tests itself: its gate re-proves them on the red tree (WP-151 A).
        return []
    return moved


def record_red_tree(result, cwd, runs, story_id):
    """At the test gate's pass: the tree as it is, when every mapped test was red in this run. A pass that let a test
    through green — a back round after the build, a decision — has production code past the red state: the tree an
    earlier pass recorded stays, since tidy's tests are laid over it anyway."""
    if any(c == "tests-red" and st == "pass" and " is green now" in m for st, c, m in result.entries):
        return
    tree = git_tree(cwd)
    if tree:
        write_mark(runs, story_id, RED_TREE, tree)


def is_test_path(path):
    """A test file by its name, or any file below a test folder — the support a test uses beside the tests."""
    parts = path.replace("\\", "/").split("/")
    return bool(TEST_FILE.search(parts[-1])) or any(TEST_DIR.search(part) for part in parts[:-1])


@contextlib.contextmanager
def red_tree_copy(cwd, runs, tree):
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


def reprove_red(result, profile, cwd, runs, story_id, mapping, located):
    """WP-151 A, at the tidy gate: a test tidy moved — a copy lifted into the support, a page object called instead of
    a raw locator — is run on the red tree with the working tree's tests laid over it. Red there (an assertion's red,
    not a timeout), its new version carries the proof: the ledger takes its digest and the journal a `red-reproved`
    line. Green there, or not compiling (tidy renamed production code the test calls), it is refused."""
    if answered_decisions(cwd, story_id, "test"):
        return
    moved = tidy_moves(cwd, runs, story_id, located)
    tree = red_tree(runs, story_id)
    if not moved or not tree:
        return
    keys = {selector: key for key, selectors in (mapping or {}).items() for selector in selectors}
    table = {}
    for selector in moved:
        table.setdefault(keys.get(selector, "moved by tidy"), []).append(selector)
    with red_tree_copy(cwd, runs, tree) as copy:
        built = Result()
        check_compiles(built, profile, copy)
        if built.failed:
            take(result, (BreakChecks.reproof_uncompiled(
                tuple(Selector(s) for s in moved),
                Detail("\n".join(m for st, _c, m in built.entries if st == "fail")[-600:])),))
            return
        probe = Result()
        check_test_state(probe, profile, copy, table, "red", {s: located[s] for s in moved})
    proved = []
    for selector in moved:
        seen = tuple(f for f in findings_of(probe, "tests-red") if selector in f.said.value)
        timed_out = Presence.PRESENT if any(f.state is FindingState.NOTE for f in seen) else Presence.ABSENT
        found = BreakChecks.reproof(Selector(selector), BreakChecks.verdict(seen), timed_out)
        take(result, (found,))
        if found.state is FindingState.PASS:
            proved.append(selector)
    if proved:
        digests = read_red_digests(runs, story_id)
        write_red_ledger(runs, story_id, set(proved), located, cwd,
                         kept={s: d for s, d in digests.items() if s not in proved})
        for selector in proved:
            with contextlib.suppress(OSError):
                journal_append(runs, story_id, "red-reproved", selector, "by=tidy")


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


def check_decisions(result, runs, story_id, cwd, gating=None, story_path=None, story=None):
    """Every question this story raised is recorded, and every answer it got has been applied (`DecisionChecks`): an
    answer applied is stamped in its record and becomes an `answered:` line of the story before it is said."""
    try:
        if story is None:
            path = story_path or find_story(place("epics"), story_id)
            front, body = read_front_matter(path)
            story = stage_story(story_id, path, front, body, ())
        checked = DecisionChecks.check(story, StageName(gating or ""), StageEvidenceFiles(cwd, runs, place("epics"), {}))
    except GateError as error:
        result.fail("decisions", str(error))
        return
    stamps = DecisionStampFiles(runs)
    for item in checked.items:
        take(result, (DecisionChecks.applied(item, stamps.apply(story, item)),) if isinstance(item, Applying) else (item,))


# The same checks outside a story: a direct edit, a commit and CI get one verdict for one tree. The
# profile declares the commands; its `required:` line declares which of them must hold. Without
# that line the check reports what it ran and what it skipped, and fails only on a red command.


def red(result, check, message, must, strict):
    """A red check fails the verdict — unless a policy is declared and this check is not in it (`suite_checks.red`)."""
    take(result, (red_finding(CheckName(check), Said(message), Presence.PRESENT if must else Presence.ABSENT,
                              Presence.PRESENT if strict else Presence.ABSENT),))


def run_test_command(result, cwd, profile, key, command, required, strict=False, owner=None):
    """A test command passes only when its reports show it executed tests and none failed. With `owner` (a story's
    whole suite) a red test outside the story runs again alone once."""
    judge_suite(result, suite_run(cwd, profile, key, command, owner), required, strict)


def judge_suite(result, suite, required, strict=False):
    """A suite's run judged (`SuiteChecks.suite`); a test noted flaky is carried in the result."""
    judged = SuiteChecks.suite(suite, Presence.PRESENT if required else Presence.ABSENT,
                               Presence.PRESENT if strict else Presence.ABSENT)
    take(result, judged.findings)
    result.flaky += [test.value for test in judged.flaky]


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


def check_main_tests(result, cwd, runs, story_id):
    """The merge's resolution kept the main line's side of every test it met (`IntegrationChecks.main_tests`)."""
    take(result, IntegrationChecks.main_tests(stage_story(story_id, "", {}, "", ()),
                                              StageEvidenceFiles(cwd, runs, place("epics"), {})))


def check_existing_tests(result, cwd, runs, story_id, story_body=""):
    """The tests that existed before the story still expect what they did (`KeptChecks.tests_kept`)."""
    story = stage_story(story_id, "", {}, story_body, ())
    take(result, KeptChecks.tests_kept(story, StageEvidenceFiles(cwd, runs, place("epics"), {})))


def check_required_suites(result, profile, cwd, already=None, owner=None):
    """At build and tidy: the test commands the policy requires, run whole (`SuiteChecks`).

    The mapped tests say this story's behaviour holds; they say nothing about the behaviour the stories before it
    delivered. Without a policy the stage gates stay as they were. A command the test-state check already ran whole
    (`already`: `{command: (key, code, output, ran)}`) is judged from that run — one process per command per gate,
    not two."""
    already = already or {}
    commands = suite_commands(profile)
    take(result, SuiteChecks.required(commands))
    required = {key.value for key in commands.required}
    seen = set()
    for key in [k for k in test_command_keys(profile) if k in required and profile.get(k)]:
        if profile[key] in seen:
            continue
        seen.add(profile[key])
        before = len(result.entries)
        if profile[key] in already:
            _key, code, output, ran = already[profile[key]]
            judge_suite(result, suite_run(cwd, profile, key, profile[key], owner, (code, output, ran),
                                          reused=" (the run the mapped tests were read from)"), True, True)
        else:
            run_test_command(result, cwd, profile, key, profile[key], True, True, owner=owner)
        result.entries[before:] = [(state, "suite" if check != "flaky" else check, message)
                                   for state, check, message in result.entries[before:]]


def change_check(result, cwd, profile, staged, only):
    """The profile's checks outside a story (`ChangeChecks`): a direct edit, a commit (`staged`: the index, refused
    where the working tree differs) and CI get one verdict for one tree."""
    required = set(split_list(profile.get("required")))
    strict = Presence.PRESENT if required else Presence.ABSENT
    take(result, ChangeChecks.policy(frozenset(CommandKey(r) for r in required)))
    env = dict(os.environ)
    tree = None
    paths = backlog_paths(cwd, env) if staged and not split_list(only) else None
    if staged:
        if paths and not split_list(profile.get("checks.backlog")):
            take(result, (ChangeChecks.backlog_alone(),))
        else:
            index = snapshot(cwd, env)
            found = ChangeChecks.snapshot(index)
            take(result, (found,))
            if found.state is not FindingState.PASS:
                return
            tree = index.tree.value
        # The profile's commands must not inherit a temporary index (`git commit -a`): a test that
        # runs git in a repository of its own would read this commit's index as its own.
        os.environ.pop("GIT_INDEX_FILE", None)
    else:
        code, head = git(cwd, "rev-parse", "--short", "HEAD", env=env)
        take(result, (ChangeChecks.working_tree(Detail(head) if code == 0 else None),))
    scope = split_list(only) or list(CHANGE_CHECKS)
    test_keys = [k for k in test_command_keys(profile)] + sorted(
        r for r in required if (r == "e2eTest" or r.startswith("test.")) and r not in test_command_keys(profile))
    # A commit of the backlog alone — stories, decisions, findings, the pipeline's protocol — changes no code: it
    # runs what `checks.backlog` names (a project whose tests read the backlog names them), by each check's or
    # test command's own key, and nothing more. An explicit `--checks` scope is the person's and wins.
    test_scope = None
    if paths:
        named = split_list(profile.get("checks.backlog"))
        take(result, ChangeChecks.backlog_scope(tuple(CommandKey(n) for n in named),
                                                tuple(CommandKey(k) for k in test_keys), Count(len(paths))))
        test_scope = {n for n in named if n in test_keys}
        scope = [n for n in named if n in CHANGE_CHECKS and n != "test"] + (["test"] if test_scope else [])
    for check in CHANGE_CHECKS:
        if check == "test":
            required_tests = [k for k in test_keys if k in required]
            if check not in scope:
                take(result, (ChangeChecks.out_of_scope(CheckName(check),
                                                        tuple(CommandKey(k) for k in required_tests)),))
                continue
            commands = {}
            for key in test_keys:
                if test_scope is not None and key not in test_scope:
                    take(result, (ChangeChecks.test_out_of_scope(CommandKey(key), Presence.PRESENT if key in required else Presence.ABSENT),))
                    continue
                if profile.get(key):
                    commands.setdefault(profile[key], []).append(key)
                elif key in required:
                    take(result, (ChangeChecks.missing_test(CommandKey(key)),))
            if not commands and not required_tests:
                take(result, (ChangeChecks.no_test(),))
            for command, keys in commands.items():
                run_test_command(result, cwd, profile, "/".join(keys), command,
                                 any(k in required for k in keys), bool(required))
            continue
        must = Presence.PRESENT if check in required else Presence.ABSENT
        if check not in scope:
            take(result, (ChangeChecks.test_out_of_scope(CommandKey(check), must),))
            continue
        command = profile.get(check)
        if not command:
            take(result, (ChangeChecks.missing(CheckName(check), CommandKey(check), must),))
            continue
        code, output = run(command, cwd)
        take(result, (ChangeChecks.command(CheckName(check), CommandRun(Detail(command), Count(code),
                                                                       Detail(tail(output)), Detail("")),
                                           must, strict),))
    if tree:
        _, after = git(cwd, "write-tree", env=env)
        if after != tree:
            take(result, (ChangeChecks.index_changed(Detail(tree), Detail(after)),))


def parity(result, config_path):
    """Every implementation's reports against one scenario contract (`ChangeChecks.parity`)."""
    take(result, ChangeChecks.parity(parity_facts(config_path)))


def acceptance_applies(cwd, runs, story_id, profile):
    """Whether this story waits for a human before it is delivered (`AcceptanceRules.asks`)."""
    mode = AcceptanceMode(acceptance_mode(profile))
    browser = str(profile.get("browser", "none")).strip().lower() not in ("", "none")
    end_user = False
    if mode is AcceptanceMode.PAGES and browser:
        with contextlib.suppress(GateError):
            located = locate_tests(cwd, read_mapping(runs, story_id)[1])[0]
            end_user = any((command_for(profile, path) or ("", ""))[0] == "e2eTest" for path in located.values())
    return AcceptanceRules.asks(mode, Presence.PRESENT if browser else Presence.ABSENT,
                                Presence.PRESENT if end_user else Presence.ABSENT) is Presence.PRESENT


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


class Result(Verdict):
    """A gate run's verdict, as the gate reports it."""

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


#: The check a gate's compile command reports under.
COMPILES = CheckName("compiles")


@check("suites")
def _suites(run):
    if not run.args.record_suites:
        return
    key = os.environ.get("FACTORY_SUITES_KEY", "")
    if key:
        commands.SUITES_RECORD = open_suites_record(run.cwd, run.runs, run.story_id, key)
    else:
        run.result.note("suites", "--record-suites without FACTORY_SUITES_KEY in the environment — nothing is "
                                  "recorded or reused")


@check("decisions")
def _decisions(run):
    check_decisions(run.result, run.runs, run.story_id, run.cwd, run.stage.name, run.story_path, run.story)


@check("plan", stages=("plan",))
def _plan(run):
    take(run.result, StoryChecks.happy_path(run.story, run.contract, run.evidence))
    take(run.result, BacklogChecks.context_map(run.story, run.evidence))
    take(run.result, ProfileChecks.instruction_size(run.evidence))
    check_project(run.result, run.cwd, run.profile)
    take(run.result, ProfileChecks.models(run.evidence))


@check("document", stages=("document",))
def _document(run):
    passed = DeliveryChecks.story_pass(run.story, run.evidence)
    take(run.result, passed.findings)
    if passed.judge_passed is Presence.PRESENT:
        record_judge_signal(run.runs, run.story_id,
                            current_stage_files(run.runs, run.story_id, order_for(run.kind))["judge"])
    take(run.result, DeliveryChecks.outcome_raised(run.story, run.contract, run.evidence))
    take(run.result, DeliveryChecks.documented(run.story, run.evidence))
    take(run.result, DeliveryChecks.proposals_landed(run.story, run.evidence))
    take(run.result, DeliveryChecks.reviews(run.story, run.evidence))


@check("adopt", stages=("adopt",))
def _adopt(run):
    check_adopt(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front, run.criteria)


@check("integrate", stages=("integrate",))
def _integrated(run):
    take(run.result, IntegrationChecks.integrated(run.story, run.evidence))
    take(run.result, IntegrationChecks.main_tests(run.story, run.evidence))
    # The spec as the main line holds it now: a key another story added meanwhile, or a criterion it changed, is a
    # question to a person — never a silent last-writer-wins (WP-98 R3). With claims on a remote the main line is the
    # remote's, merged into this worktree (WP-93 D).
    if claim_config_here(factory_home() or run.cwd):
        with places_in(run.cwd):
            check_spec_delta(run.result, run.cwd, run.runs, run.story_id, run.story_path, run.front, run.body)
    else:
        check_spec_delta(run.result, run.cwd, run.runs, run.story_id, run.story_path, run.front, run.body)


@check("tests-mapped", stages=lambda s: Trait.TESTED in s.traits, kinds=TESTED)
def _mapping(run):
    run.mapping = check_mapping(run.result, run.runs, run.story_id, run.criteria)
    run.located = check_exists(run.result, run.cwd, run.mapping)


# Integrated, the story's diff carries the main line's changes beside its own: the file list, the tests that existed
# before and the red proof were the stages' to hold, and they held.
@check("files-listed", stages=lambda s: Trait.LISTS in s.traits)
def _files_listed(run):
    take(run.result, KeptChecks.files_listed(run.story, StageName(run.stage.name), mapped_tests(run), run.evidence))
    take(run.result, KeptChecks.tests_kept(run.story, run.evidence))


@check("test-design", stages=lambda s: Trait.RED in s.traits)
def _test_design(run):
    take(run.result, TestChecks.plan_levels(run.story, run.evidence))
    tests = mapped_tests(run)
    take(run.result, DesignChecks.invariants(run.story, run.contract, tests, run.evidence))
    take(run.result, TestChecks.levels(run.story, run.contract, tests, run.evidence))
    take(run.result, DesignChecks.clauses(run.story, run.contract, tests, run.evidence))
    take(run.result, TestChecks.titles(run.story, run.contract, tests, run.evidence))


@check("tests-real", stages=("test", "adopt"))
def _tests_real(run):
    if contract_of(run.profile) >= 21:
        take(run.result, DesignChecks.tests_real(run.story, mapped_tests(run), run.evidence))


@check("red-proof", stages=lambda s: Trait.LISTS in s.traits, kinds=TESTED)
def _red_proof(run):
    # the red proof compares digests, so it belongs here, before any process
    if run.expected == "green":
        take(run.result, KeptChecks.red_proof(run.story, StageName(run.stage.name), mapped_tests(run), run.evidence))


def whole_suites(run):
    """At build and tidy the policy's required test commands run whole anyway: that run is the evidence for the mapped
    tests as well, so those commands are not started a second time."""
    if not run.stage.suite:
        return ()
    return tuple(k for k in test_command_keys(run.profile)
                 if k in set(split_list(run.profile.get("required"))) and run.profile.get(k))


@check("tests", stages=lambda s: Trait.TESTED in s.traits, needs_process=True,
       unrun=lambda run: ["compiles", f"tests-{run.expected}"] + (["suite"] if run.stage.suite else []))
def _tests(run):
    check_compiles(run.result, run.profile, run.cwd)
    owner = SuiteOwner(run.runs, run.story_id, run.mapping or {})
    if run.kind == "task":
        check_task_suites(run.result, run.profile, run.cwd, owner)
        return
    run.whole_runs = check_test_state(run.result, run.profile, run.cwd, run.mapping, run.expected, run.located,
                                      run.runs, run.story_id, guard=run.kind in ("journey", "adopt"),
                                      whole_for=whole_suites(run), red_proof=False)
    if run.stage.suite:
        check_required_suites(run.result, run.profile, run.cwd, run.whole_runs, owner)


@check("invariant-breaks", stages=("test",), needs_process=True, kinds=frozenset((StoryKind.STORY,)))
def _invariant_breaks(run):
    if contract_of(run.profile) >= 25:
        check_invariant_breaks(run.result, run.profile, run.cwd, run.runs, run.story_id, run.mapping)


@check("red-reproof", stages=("tidy",), needs_process=True, kinds=frozenset((StoryKind.STORY,)))
def _red_reproof(run):
    reprove_red(run.result, run.profile, run.cwd, run.runs, run.story_id, run.mapping, run.located)


@check("commands", stages=lambda s: bool(s.commands), needs_process=True,
       unrun=lambda run: [key for key in run.stage.commands if run.profile.get(key)])
def _commands(run):
    check_stage_commands(run.result, run.profile, run.cwd, run.stage.name)


@on_pass("plan")
def _plan_passed(run):
    if is_delivered(run.front):
        # Delivered is delivered: a plan gate run over a delivered story (a check, a re-verification) leaves the
        # story and the marks the delivery rests on as they are.
        run.result.note("story", f"{run.story_id} is delivered — checked, its marks are left as they are")
    else:
        write_mark(run.runs, run.story_id, STORY_DIGEST, story_digest(run.story_path))
        record_tests_baseline(run.cwd, run.runs, run.story_id)
        plan = os.path.join(run.runs, run.story_id, "plan.md")
        journal_signal(run.runs, run.story_id, "plan", open=len(plan_left_open(read_text(plan))) if os.path.isfile(plan) else 0)


def record_flaky_findings(result, story_path, story_id, front, runs):
    """WP-113: a test noted flaky in this story and in another one is a finding — a row of the project's own findings
    (`<product>/findings/flaky.md`, WP-146: the flake belongs to no one story), open, for a task (`kind: task`,
    `closes: flaky#<n>`) that fixes the flake instead of running it again for ever. One open row per test across the
    backlog."""
    mine = set(flaky_tests(runs, story_id)) | set(result.flaky)
    root = evidence_dir(runs)
    if not mine or not os.path.isdir(root):
        return
    others = {}
    for other in sorted(os.listdir(root)):
        if other != story_id and os.path.isdir(os.path.join(root, other)):
            for test in flaky_tests(runs, other):
                others.setdefault(Detail(test), []).append(StoryId(other))
    open_rows = set()
    with contextlib.suppress(GateError, OSError):
        open_rows = {where for _s, where, _sev, _d, perspective, _f, _p in open_findings(place("epics"))
                     if perspective == "flaky"}
    added = [("flaky", f.test.value, "minor", f.defect.value, f.fix.value, f.plain.value)
             for f in AcceptanceRules.flaky(StoryId(story_id), frozenset(Detail(t) for t in mine),
                                            {t: tuple(s) for t, s in others.items()},
                                            frozenset(Detail(w) for w in open_rows))]
    if added:
        path = project_findings_path(FLAKY_FINDINGS)
        append_finding_rows(path, project_findings_head(FLAKY_FINDINGS), added)
        result.written.append(path)
        result.ok("findings", f"{len(added)} flaky test(s) noted in two stories kept as a finding in "
                              f"{shown(path)}: {', '.join(r[1] for r in added)}")


@on_pass("test")
def _test_passed(run):
    if run.kind == "story" and not is_delivered(run.front):
        record_red_tree(run.result, run.cwd, run.runs, run.story_id)


@on_pass("document")
def _document_passed(run):
    result, story_id, story_path = run.result, run.story_id, run.story_path
    if is_delivered(run.front):
        # Delivered is delivered: a document gate run over a delivered story checks it and leaves the story's
        # `delivered:` date as it is.
        result.note("story", f"{story_id} is delivered — checked, its marks are left as they are")
        return
    try:
        if run.kind != "task" and acceptance_applies(run.cwd, run.runs, story_id, run.profile):
            verdict, rid = acceptance_state(run.cwd, story_id, story_path)
            step = AcceptanceRules.at_delivery(Acceptance(AcceptanceVerdict(verdict), RecordId(rid) if rid else None))
            take(result, step.findings)
            if step.ask is Presence.PRESENT:
                asked = ask_acceptance(run.cwd, run.runs, story_id, story_path, run.profile, run.criteria)
                take(result, AcceptanceRules.asked(Detail(asked), Detail(shown(record_path(story_id, asked, story_path)))))
            if step.goes_on is Presence.ABSENT:
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
    deliver(result, story_path, story_id, run.front, run.runs)


@on_pass("adopt")
def _adopt_passed(run):
    if is_delivered(run.front):
        return
    if in_worktree():
        run.result.ok("integrate", f"every check passed — {run.story_id} is adopted once its tests are integrated "
                                   f"into the main checkout (the runner's integrate step)")
        return
    deliver(run.result, run.story_path, run.story_id, run.front, run.runs)


@on_pass("integrate")
def _integrate_passed(run):
    config = claim_config_here(factory_home() or run.cwd)
    if config:
        publish_story(run.result, run.cwd, run.story_path, run.story_id, run.front, run.runs, config)
    else:
        integrate_into_home(run.result, run.cwd, run.story_path, run.story_id, run.front, run.runs,
                            close=lambda: close_record(run))


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
                        help="check the discovery report of one topic (product/discovery/<topic>/) and exit")
    parser.add_argument("--check-backlog", action="store_true",
                        help="the plan gate's backlog checks over every story that is not done (or --story), "
                             "writing nothing, and exit")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`, else product/epics)")
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
            folder = location(read_profile(resolve_profile(args.profile, cwd)), "discovery")
            checked = check_report(cwd, folder, args.check_discovery)
            (result.ok if checked.passed else result.fail)("discovery", checked.said)
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
        criteria = criteria_of(story_path, body, front)
        run = gate_run(result=result, args=args, cwd=cwd, runs=args.runs, stage=STAGE[args.stage], story_id=story_id,
                      story_path=story_path, front=front, body=body, criteria=criteria,
                      profile=read_profile(resolve_profile(args.profile, cwd)))
        run_checks(run)
    except GateError as error:
        result.fail("gate", str(error))
        return journal_gate(result, args, story_id, story_path, result.report(args.story, args.stage, args.json,
                                                                              args.brief))
    if not result.failed:
        run_passed(run)
    return journal_gate(result, args, story_id, story_path, result.report(story_id, args.stage, args.json, args.brief))


def integrate_into_home(result, cwd, story_path, story_id, front, runs, close=None):
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
    if done.returncode != 0 and git(home, "merge-base", "--is-ancestor", "HEAD", head)[0] != 0:
        # The main line moved between the merge and here — a person's commit, another story integrated: the
        # integrate step merges it again and holds the story to the gate once more, as for a target moved earlier.
        result.fail("moved", f"{target} moved on while the story was held to the gate — the integrate step merges "
                             f"again")
        return
    if done.returncode != 0:
        result.fail("checkout", f"the main checkout could not take the story's commit: "
                                f"{(done.stderr or done.stdout).strip().splitlines()[0] if (done.stderr or done.stdout).strip() else 'git refused'}"
                                f" — commit or stash what is in the way there, then "
                                f"`factory.sh run --story {story_id} --from integrate`")
        return
    result.ok("integrated", f"{target} took the story's commit {head[:12]}")
    deliver(result, story_path, story_id, front, runs)
    if not result.failed:
        commit_delivery(result, home, story_id, front, close)


def story_journals(home):
    """The story journals a commit takes along — every one git does not ignore (WP-150: the journal is the record,
    committed): what a delivery and a request wrote into them goes with what they wrote."""
    found = []
    for journal in sorted(glob.glob(os.path.join(home, evidence_rel(), "*", JOURNAL))):
        rel = os.path.relpath(journal, home).replace("\\", "/")
        if git(home, "check-ignore", "-q", "--", rel)[0] != 0:
            found.append(rel)
    return found


def commit_delivery(result, home, story_id, front, close=None):
    """What the delivery wrote on the main line — the story's folder (its state, decisions, findings) and the spec
    it merged — committed there beside the story's commit, so the next story's worktree starts from it. Only those
    paths: what else the main checkout holds, staged or not, stays as it is. `close` writes the delivery's own last
    events first: the commit carries the story's whole record, and nothing of the delivery is written after it."""
    if close:
        close()
    paths = []
    for path in dict.fromkeys(result.written):
        rel = os.path.relpath(os.path.abspath(path), home).replace("\\", "/")
        if not rel.startswith("../") and (os.path.exists(os.path.join(home, rel)) or git(home, "ls-files", "--", rel)[1]):
            paths.append(rel)
    paths += story_journals(home)
    if not paths:
        return
    git(home, "add", "-A", "--", *paths)
    if git(home, "diff", "--cached", "--quiet", "HEAD", "--", *paths)[0] == 0:
        return
    scope = re.sub(r"[^a-z0-9]+", "-", str(front.get("context", "")).lower()).strip("-") or "story"
    done = git(home, *git_identity(home), "commit", "--no-verify", "--quiet", "-m",
               f"chore({scope}): deliver {story_id}\n\nStory: {story_id}\n", "--", *paths)
    if done[0] != 0:
        result.fail("committed", f"the delivery's files could not be committed on the main line: {done[1][:300]} — "
                                 f"commit {', '.join(paths)} by hand")
        return
    result.ok("committed", f"the delivery's files committed on the main line: {', '.join(paths)}")


def check_spec_delta(result, cwd, runs, story_id, story_path, front, body):
    """The plan's spec delta against the story and the spec (`SpecChecks.delta`)."""
    story = stage_story(story_id, story_path, front, body, ())
    take(result, SpecChecks.delta(story, StageEvidenceFiles(cwd, runs, place("epics"), {})))


def check_spec_tests(result, cwd, runs, story_id, front, mapping):
    """Every test the story's spec names is still there (`SpecChecks.tests`)."""
    take(result, SpecChecks.tests(stage_story(story_id, "", front, "", ()), table_tests(mapping),
                                  StageEvidenceFiles(cwd, runs, place("epics"), {})))


def check_tests_committed(result, cwd, front, mapping, runs=""):
    """The story's commit holds every test file its mapping and its spec name (`SpecChecks.committed`)."""
    take(result, SpecChecks.committed(stage_story("", "", front, "", ()), table_tests(mapping),
                                      StageEvidenceFiles(cwd, runs, place("epics"), {})))


def merge_spec(result, story_path, story_id, front, runs):
    """The delivering gate's merge (WP-98, WP-105): the story's delta into its context's spec, by key, with the test
    lines from tests.md — the story's criteria into its feature's file, a moved one out of the file it stood in, a
    removed one gone wherever it stood; a feature file left without a criterion goes. Deterministic, nothing a stage
    writes. The story is history from here on."""
    _front, body = read_front_matter(story_path)
    target, spec, _features, feature = story_spec(front)
    if not target:
        return
    plan = os.path.join(runs, story_id, "plan.md")
    delta = read_delta(read_text(plan)) if os.path.isfile(plan) else read_delta("")
    try:
        mapping = read_mapping(runs, story_id)[1]
    except GateError:
        mapping = {}
    tests = dict(mapping)
    for key, selectors in moved_tests(runs, story_id).items():
        tests.setdefault(key, selectors)        # a criterion of the story keeps the test its mapping names
    story = story_entries(body)
    context = str(front.get("context", "")).strip()
    journey = story_kind(front) == "journey"
    merged = {"": merge(spec, story, delta, tests)} if journey else merge_context(spec, story, delta, tests, feature)
    for entries in merged.values():
        for item in entries:
            if item["key"] in tests and item["key"] not in {s["key"] for s in story}:
                item["tests"] = tests[item["key"]]
    if not journey:
        # The spec as it will stand, checked before a line is written: a delivery never leaves it malformed.
        texts = {name: render_spec(read_spec(scenarios_path(context, name))[0], entries,
                                   f"{context} — {name}" if name else context)
                 for name, entries in merged.items() if entries or not name}
        problems = lint_context(context, texts)
        if problems:
            result.fail("spec", f"the spec after this story would not hold its shape: {'; '.join(problems[:6])}"
                                + (" …" if len(problems) > 6 else "") + " — nothing written")
            return False
    written = []
    for name, entries in sorted(merged.items()):
        path = target if journey else scenarios_path(context, name)
        if not entries and name:
            if os.path.isfile(path):
                os.remove(path)
                with contextlib.suppress(OSError):
                    os.rmdir(os.path.dirname(path))
                written.append(f"{shown(path)} (gone — no criterion left)")
                result.written.append(path)
            continue
        if not entries and not os.path.isfile(path):
            continue
        preamble = read_spec(path)[0]
        title = "Journeys" if journey else f"{context} — {name}" if name else context or "Spec"
        text = render_spec(preamble, entries, title)
        if not os.path.isfile(path) or read_text(path) != text:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            written.append(shown(path))
            result.written.append(path)
    found = derived(story, spec)
    result.ok("spec", f"{', '.join(written) or shown(target)}: {sum(v == 'adds' for v in found.values())} added, "
                      f"{sum(v == 'changes' for v in found.values())} changed, {len(delta['removes'])} removed"
                      + (f", {len(delta['moves'])} moved" if delta["moves"] else "")
                      + (f", {len(delta['renames'])} rule(s) renamed" if delta["renames"] else ""))


@contextlib.contextmanager
def places_in(cwd):
    """The epics and the spec read from this worktree, not the main checkout — where the remote main line is what
    the story was merged with (WP-93 D)."""
    home = factory_home() or cwd
    saved = dict(PLACES)
    try:
        for key in ("epics", "spec"):
            own = saved.get(key) or DEFAULTS[key]
            PLACES[key] = os.path.join(cwd, os.path.relpath(own if os.path.isabs(own) else os.path.join(home, own), home))
        yield
    finally:
        PLACES.clear()
        PLACES.update(saved)


def publish_story(result, cwd, story_path, story_id, front, runs, config):
    """WP-93 D: the factory never moves `main`. The delivering function writes into the story's worktree — the story's
    three state lines and the merge into the spec —, the squashed commit takes them, and the story branch is pushed
    with a lease on what this factory pushed last: only its own claim can be overwritten. A person merges it; the
    remote main line then says delivered for every factory."""
    home = factory_home() or cwd
    rel_story = os.path.relpath(story_path, home)
    local_story = os.path.join(cwd, rel_story)
    spec_rel = os.path.relpath(place("spec") if os.path.isabs(place("spec")) else os.path.join(home, place("spec")), home)
    with places_in(cwd):
        before = read_front_matter(local_story)[0]
        mark = os.path.join(evidence_dir(runs, story_id), "published-status")
        with open(mark, "w", encoding="utf-8") as handle:
            handle.write(str(before.get("status", "")).strip() + "\n")
        deliver(result, local_story, story_id, before, runs)
    git(cwd, "add", "-A", "--", spec_rel, os.path.dirname(rel_story))
    if git(cwd, *(["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
                  if not git(cwd, "config", "user.email")[1].strip() else []),
           "commit", "--amend", "--no-edit", "--no-verify", "--quiet")[0] != 0:
        result.fail("published", f"the delivery could not be added to {story_id}'s commit")
        return
    remote, prefix = config["remote"], config["prefix"]
    ref = f"refs/heads/{prefix}{story_id}"
    known = git(cwd, "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{prefix}{story_id}")
    lease = f"--force-with-lease={ref}:{known[1].strip()}" if known[0] == 0 else f"--force-with-lease={ref}:"
    code, out = git(cwd, "push", "--porcelain", lease, remote, f"HEAD:{ref}")
    if code != 0:
        result.fail("published", f"{remote} refused {prefix}{story_id}: {' '.join(out.split())[:300]} — another "
                                 f"factory's commit is there, or a branch rule; needs-human")
        return
    head = git(cwd, "rev-parse", "HEAD")[1].strip()
    with open(os.path.join(evidence_dir(runs, story_id), PUBLISHED), "w", encoding="utf-8") as handle:
        handle.write(head + "\n")
    result.ok("published", f"{prefix}{story_id} on {remote} carries the story as one commit {head[:12]} — delivered on "
                           f"its branch; `main` is not moved: a person merges it (merge request or push)")


def deliver(result, story_path, story_id, front, runs):
    """The one write a delivering gate makes into a story — the document gate, the adopt gate and, in a story's
    worktree, the integrate gate all call it. One end state: built or adopted, the story reads `status:
    delivered`, `delivered:` and `delivered_by: gate`; an adopted story is no longer `adopted` (that was its
    input: "the code exists, check it"). The judge's confirmed defects that did not block are kept beside it."""
    if story_kind(front) == "task":
        close_findings(result, front)
    elif merge_spec(result, story_path, story_id, front, runs) is False:
        return
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    story = StoryFiles.read(story_path)
    story.deliver_by_gate(Moment(stamp))
    StoryFiles.write(story_path, story)
    result.written.append(story_folder(story_path))
    result.ok("delivered", f"{shown(story_path)} carries `status: delivered`, `delivered: {stamp}`, "
                           f"`delivered_by: gate`")
    added, open_now = record_findings(story_path, story_id, front, runs)
    if added or open_now:
        result.ok("findings", f"{added} confirmed finding(s) kept in {shown(findings_path(story_path))} — "
                              f"{open_now} open there")
    record_flaky_findings(result, story_path, story_id, front, runs)
    judge = os.path.join(runs, story_id, "judge.md")
    unworded = [r[1] for r in confirmed_defects(read_text(judge)) if not r[5]] if os.path.isfile(judge) else []
    if unworded:
        result.note("findings", f"{len(unworded)} confirmed defect(s) in judge.md without `{PLAIN_COLUMN}` "
                                f"({', '.join(unworded[:3])}{' …' if len(unworded) > 3 else ''}) — the one sentence a "
                                f"person reads first; Decide shows the reviewer's `Defect` in its place")


def close_record(run):
    """A delivery's last events, journaled before its commit: the gate's passing verdict and the end of the runner's
    integrate step it runs in, where that step is open. The commit then holds the story's record whole — a delivered
    story leaves no journal line behind in the checkout. A commit that fails after it is journaled as the refusal."""
    journal_append(run.runs, run.story_id, "gate", run.args.stage, *gate_fields(run.result, run.args, 0))
    run.result.closed = True
    if step_open(run.runs, run.story_id, "integrate"):
        journal_append(run.runs, run.story_id, "step-end", "integrate", "exit=0")


def gate_fields(result, args, code):
    """A gate run's event fields: `exit=<code> fail=<checks> by=<who>` — the runner's (`by=runner`, the one that
    signs suites), a stage's own under a runner (`by=<stage>`), a session's (`by=session`)."""
    failed = sorted({check for state, check, _ in result.entries if state == "fail"})
    by = "runner" if args.record_suites else (os.environ.get("FACTORY_STAGE") or "stage") \
        if os.environ.get("FACTORY_WORKER") else "session"
    fields = [f"exit={code}"] + ([f"fail={','.join(failed)}"] if failed else []) + [f"by={by}"]
    if result.flaky:
        fields.append(f"flaky={','.join(dict.fromkeys(result.flaky))}")
    return fields


def journal_gate(result, args, story_id, story_path, code):
    """Every gate run over a story is an event (`gate_fields`); a delivery journaled its passing verdict before its
    commit (`close_record`). The plan gate's refusal carries the backlog's digest, so a repair is seen without a
    clock."""
    if not story_id or code == 0 and result.closed:
        return code
    fields = gate_fields(result, args, code)
    if args.stage == "plan" and code == 1 and story_path:
        fields.append(f"backlog={backlog_digest(story_path)}")
    with contextlib.suppress(OSError):
        journal_append(args.runs, story_id, "gate", args.stage, *fields)
    return code
