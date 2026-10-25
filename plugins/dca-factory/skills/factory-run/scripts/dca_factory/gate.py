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
import collections
import contextlib
import difflib
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
    ALL_KINDS, CONTRACT, CRITERION, GateError, layout_hint, MAPPING_ROW, order_for, SELECTOR, STAGE, STAGE_CHECKS, STAGE_FILES, STAGES, TESTED_KINDS, VERSION)
from .delivery.adapter.outgoing.files.findings_files import (
    append_finding_rows, confirmed_defects, findings_cells, findings_path, open_findings,
    PLAIN_COLUMN, project_findings_head, project_findings_path, record_findings)
from .delivery.adapter.outgoing.files.story_layout import (
    duplicate_ids, file_digest, find_story, is_delivered, story_digest,
    story_files, story_folder, story_id_of, story_kind)
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, evidence_dir, evidence_rel, factory_home, findings_rel, FLAKY_FINDINGS, HOME_VARIABLE, in_worktree,
    JOURNAL, location, place, PLACES, PLACES_REL, PROFILE_FILE, read_profile,
    resolve_profile, runs_top, set_places, shown)
from .delivery.adapter.outgoing.git.repository import git, git_blob, git_identity
from .delivery.adapter.outgoing.files.decision_record_files import (
    answered_decisions, decisions_store, NOTHING, project_decisions_rel, record_path,
    records_of)
from .delivery.adapter.outgoing.files.decision_record_files import needs_human_ids
from .delivery.domain.model.correction import REASON_CODES
from .delivery.application.description.check_description import CheckDescriptionCommand
from .discovery.api import check_report
from .infrastructure.description import check_description
from .sharedkernel.adapter.outgoing.markdown.sections import section_of
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .delivery.adapter.outgoing.build.test_reports import (
    clock_marker, display_name_of, executed_tests, fill, normalise, outcome_for, read_scenarios, report_state,
    reported_names, reports_from_this_run, SENTINEL, unescape_literal)
from .spec.api import (
    context_files, delta_problems, derived, feature_name, journeys_path, merge, merge_context, placement_problems, rule_problems,
    lint_context, read_context, read_delta, read_spec, render_spec, scenarios_path, story_entries,
    touches)
from .delivery.adapter.outgoing.claims.remote_claims import claim_config_here, PUBLISHED, remote_main
from .delivery.adapter.outgoing.files.story_record import INVARIANT_BREAKS
from .delivery.adapter.outgoing.files.signals import journal_signal, latest_signal, plan_left_open, record_judge_signal
from .delivery.adapter.outgoing.files.snapshots import (
    git_tree, NOT_OBSERVED, record_base, record_changes)
from .delivery.adapter.outgoing.files.owned_files import owned_end, run_owned
from .delivery.adapter.outgoing.files.run_marks import (
    backlog_digest, current_stage_files, last_ended, step_open,
    STORY_DIGEST, verdict_in, write_mark)
from .delivery.adapter.outgoing.files.owned_files import observe_writes, record_owned, write_story_fields
from .delivery.adapter.outgoing.files.journal_files import flaky_tests, journal_append, journal_events
from .delivery.adapter.outgoing.files.decision_record_files import (
    ACCEPTANCE_KIND, acceptance_mode, acceptance_records, acceptance_state, accepted)
from .delivery.application.shared.front import is_acceptance
from .delivery.domain.model.verdict import FindingState
from .delivery.domain.service.backlog_checks import BacklogChecks
from .delivery.domain.service.profile_checks import MODEL_TOOLS, ProfileChecks  # noqa: F401 — MODEL_TOOLS: read by the verify suite
from .delivery.domain.service.story_checks import StoryChecks
from .delivery.domain.service.decision_checks import Applying, DecisionChecks
from .delivery.domain.model.stage import StageName
from .delivery.domain.model.stage_story import (
    CommandKey, Count, HandOverName, MappedTest, Place, ScenarioKey, Selector, TestTable, TitleCheck, TitleFound)
from .delivery.domain.model.story_state import Detail
from .delivery.domain.service.design_checks import DesignChecks
from .delivery.domain.service.kept_checks import KeptChecks
from .delivery.domain.service.test_checks import HANDOVER_BUDGET, TestChecks  # noqa: F401 — HANDOVER_BUDGET: read by the runner
from .delivery.adapter.outgoing.files.test_files import locate_tests
from .delivery.adapter.outgoing.files.stage_evidence_files import DecisionStampFiles, StageEvidenceFiles, stage_story, closed_rows, closes_of, happy_paths, publishes_of, split_list
from .delivery.adapter.outgoing.files.test_files import read_mapping
from .delivery.adapter.outgoing.files.design_files import BREAK_IGNORE, STEP, locate_selector, read_invariant_rows
from .delivery.adapter.outgoing.files.kept_files import RED_TREE, bare_path, human_line, meaningful_lines, read_red_digests, red_ledger_path, red_tree, row_cells, tidy_moves, unproven_tests
from .delivery.adapter.outgoing.files.kept_files import TESTS_BASELINE


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
    keys = [key for key in test_command_keys(profile) if profile.get(key)]
    if not keys:
        result.fail("suite", "a task proves itself on the existing suite, and the stack profile declares no test "
                             "command — declare `test:` (and its siblings)")
        return
    seen = set()
    for key in keys:
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
    # A story's worktree links the pipeline, the runs and the epics to the checkout's own folders; the index
    # still lists the files below such a link. The copy takes the link and nothing below it — a file copied
    # through the link would be copied onto itself.
    linked = set()
    for name in sorted({n for n in listed.stdout.decode("utf-8", "replace").split("\0") if n}):
        source, target = os.path.join(cwd, name), os.path.join(copy, name)
        parts = name.split("/")
        if any("/".join(parts[:i]) in linked for i in range(1, len(parts))):
            continue
        if not os.path.lexists(source):
            continue                          # deleted in the tree, still in the index
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
            linked.add(name)
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
    if wanted:
        with break_copy(cwd) as copied:
            for selector in wanted:
                check_break(result, profile, cwd, runs, story_id, selector,
                            by_selector.get(selector, "outside the table"), located, copied)
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


def break_verdict(seen):
    """('red' | 'green' | 'unchecked', what to add) from the tests-red entries of a break's run. A note — red on a
    timeout — gives no verdict of its own: red is red, and the note travels with it."""
    verdicts = [(st, m) for st, m in seen if st in ("pass", "fail")]
    notes = [m for st, m in seen if st == "note"]
    if verdicts and all(st == "pass" for st, _m in verdicts):
        return "red", (" — " + notes[0][:300]) if notes else ""
    if any(st == "fail" and ("passes" in m or "is green" in m or "green before" in m) for st, m in verdicts):
        return "green", ""
    return "unchecked", "; ".join(m for st, m in seen if st != "pass")[:300] or "no run of it was recorded"


def break_patch(runs, story_id, selector):
    """The break a selector has — under its full name or its simple class —, or None."""
    patch = break_path(runs, story_id, selector)
    if not os.path.isfile(patch):
        short = selector.split("#")[0].rsplit(".", 1)[-1] + "#" + selector.split("#", 1)[-1]
        patch = break_path(runs, story_id, short) if os.path.isfile(break_path(runs, story_id, short)) else patch
    return patch if os.path.isfile(patch) else None


def apply_break(copy, scratch, patch, reverse=False):
    """`git apply` of a break on the scratch copy (`-R` to take it back): (exit code, what git said). An editor on
    Windows writes the patch with CRLF, which git reads as part of each line — retried with LF."""
    args = ["git", "apply", "--whitespace=nowarn"] + (["-R"] if reverse else [])
    applied = subprocess.run(args + [os.path.abspath(patch)], cwd=copy, capture_output=True, text=True)
    with open(patch, "rb") as handle:
        raw = handle.read()
    if applied.returncode != 0 and b"\r\n" in raw:
        unix = os.path.join(scratch, "break.patch")
        with open(unix, "wb") as handle:
            handle.write(re.sub(rb"\r+\n", b"\n", raw))
        applied = subprocess.run(args + [unix], cwd=copy, capture_output=True, text=True)
    return applied.returncode, (applied.stderr or applied.stdout).strip()


def run_break(profile, copy, scratch, patch, selector, key, located):
    """One break on a scratch copy the caller made: applied, the one test run, taken back — so the next break on the
    same copy builds on what this one compiled. ('red' | 'green' | 'unchecked' | 'unapplied', what to add)."""
    code, said = apply_break(copy, scratch, patch)
    if code != 0:
        return "unapplied", said[:200]
    try:
        probe = Result()
        check_test_state(probe, profile, copy, {key: [selector]}, "red",
                         {selector: located.get(selector)} if located.get(selector) else {})
        return break_verdict([(st, m) for st, c, m in probe.entries if c == "tests-red"])
    finally:
        apply_break(copy, scratch, patch, reverse=True)


@contextlib.contextmanager
def break_copy(cwd):
    """One scratch copy of the project for every break of a gate run (WP-148): the first break compiles it, the ones
    after it build on that. Removed afterwards; the tree is never touched."""
    scratch = tempfile.mkdtemp(prefix="dca-break-")
    try:
        copy = os.path.join(scratch, "tree")
        copy_for_break(cwd, copy)
        yield copy, scratch
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check_break(result, profile, cwd, runs, story_id, selector, key, located, copied=None):
    patch = break_patch(runs, story_id, selector)
    if not patch:
        result.fail("break-proof", f"{selector} ({key}): no break at "
                                   f"{os.path.relpath(break_path(runs, story_id, selector), cwd)} — a test that is "
                                   f"green without ever being seen red (one an adoption wrote, one strengthened after "
                                   f"its build) is shown to work by one change to the code that turns it red")
        return
    with (contextlib.nullcontext(copied) if copied else break_copy(cwd)) as (copy, scratch):
        verdict, said = run_break(profile, copy, scratch, patch, selector, key, located)
    if verdict == "red":
        result.ok("break-proof", f"{selector} ({key}): red under its break, on a scratch copy{said}")
    elif verdict == "green":
        result.fail("break-proof", f"{selector} ({key}): stays green under its break — the test does not "
                                   f"notice the behaviour it claims to prove")
    elif verdict == "unapplied":
        result.fail("break-proof", f"{selector} ({key}): its break does not apply — {said}")
    else:
        result.fail("break-proof", f"{selector} ({key}): its break could not be checked — {said}")


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
    seen = {sel: break_verdict([(st, m) for st, c, m in probe.entries if c == "tests-red"
                                and (m.startswith(sel + " ") or m.startswith(sel + ":"))])[0] for sel in rules}
    verdicts = {sel: "red" for sel, v in seen.items() if v == "red"}
    green = [sel for sel, v in sorted(seen.items()) if v == "green"]
    for sel in (s for s, v in seen.items() if v not in ("red", "green")):
        verdicts[sel] = "unchecked"
    if green:
        with break_copy(cwd) as copied:
            for sel in green:
                patch = break_patch(runs, story_id, sel)
                if not patch:
                    verdicts[sel] = "no-break"
                    continue
                verdict, _said = run_break(profile, *copied, patch, sel, keys[sel], located)
                verdicts[sel] = {"red": "killed", "green": "survived", "unapplied": "no-break"}.get(verdict, "unchecked")
    write_mark(runs, story_id, INVARIANT_BREAKS, "\n".join(
        f"{e}\t{','.join(map(str, n))}\t{sel}\t{verdicts[sel]}" for sel, owners in sorted(rules.items())
        for e, n in owners))
    journal_signal(runs, story_id, "rules", [("rule", sel, dict(element=e, rules=",".join(map(str, n)),
                                                                verdict=verdicts[sel]))
                                             for sel, owners in sorted(rules.items()) for e, n in owners],
                   named=sum(len(n) for owners in rules.values() for _e, n in owners))
    for sel in sorted(rules):
        verdict, key = verdicts[sel], keys[sel]
        if verdict == "red":
            result.ok("invariant-breaks", f"{sel} ({key}): red before the build — the rule is new, its test saw it missing")
        elif verdict == "killed":
            result.ok("invariant-breaks", f"{sel} ({key}): green already, red under its break on a scratch copy")
        elif verdict == "survived":
            result.fail("invariant-breaks", f"{sel} ({key}): stays green under its break — the test does not guard "
                                            f"the rule it names")
        elif verdict == "no-break":
            result.fail("invariant-breaks", f"{sel} ({key}): green before the build, so the rule exists already, and "
                                            f"no break applies at {os.path.relpath(break_path(runs, story_id, sel), cwd)}"
                                            f" — one change to the production code that turns exactly this test red")
        else:
            result.fail("invariant-breaks", f"{sel} ({key}): no run gave it a verdict — "
                                            + "; ".join(m for st, c, m in probe.entries if sel in m)[:300])


def take(result, findings):
    """A domain check's findings into the result, as the gate reports them."""
    for finding in findings:
        getattr(result, "ok" if finding.state is FindingState.PASS else finding.state.value)(finding.check.value,
                                                                                           finding.said.value)


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


#: A source file of the project's code: the gate reads no profile key for where the code lives, so it reads every
#: file with a code extension outside the build's and the tools' folders and outside the tests.
CODE_FILE = re.compile(r"\.(java|kt|scala|groovy|cs|fs|py|ts|tsx|js|jsx|mjs|go|rb|php|rs|swift)$")


#: A test folder by name — `test`, `tests`, `test-utils`, `Foo.Tests`, and the camel-cased source set a build tool
#: names (`integrationTest`, `functionalTests`): a capital T after a lowercase letter, so `latest` and `contest` are not.
TEST_DIR = re.compile(r"(?i:^(tests?|specs?|__tests__)$|^tests?[-_.]|[-_.]tests?$)|[a-z]Tests?$")


#: A line that names a type without using it: an import, a using, a package or namespace line.
IMPORT_LINE = re.compile(r"^\s*(?:import|using|package|namespace|from\s+\S+\s+import)\b.*$", re.M)


def production_files(cwd):
    found = []
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith(".") and not TEST_DIR.search(d))
        for name in sorted(files):
            if CODE_FILE.search(name) and not TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


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
    return {"path": path, "key": key, "tree": tree, "rows": rows, "cwd": os.path.realpath(cwd)}


def recorded_run(invocation, cwd, profile=None, with_reports=False):
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


def check_story_pass(result, runs, story_id, story_path, front):
    """The document gate delivers a story, so it asks what delivery rests on: every stage of this pass
    wrote its file after the one before it, the judge passed it, and the story is the one that was planned.
    A document written for an earlier pass, or over a judge who asked for changes, delivers nothing."""
    order = order_for(story_kind(front))
    folder = os.path.join(runs, story_id)
    texts = current_stage_files(runs, story_id, order)
    gaps = [f"{STAGE_FILES[s]} ({'written for an earlier pass' if os.path.isfile(os.path.join(folder, STAGE_FILES[s])) else 'missing'})"
            for s in order if s not in texts]
    if gaps:
        result.fail("story-pass", f"{', '.join(gaps)} — the document gate delivers a story whose stages all ran, "
                                  f"in order, in this pass; the story runs on from the first of them")
        return
    verdict = verdict_in(texts["judge"])
    if verdict == "pass":
        record_judge_signal(runs, story_id, texts["judge"])
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
        check_red_proof(result, cwd, runs, located, story)
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
            result.fail("red-reproof", f"{', '.join(moved)}: tidy changed the test(s), and they do not compile on the "
                                       f"tree the test stage left — a test calls production code tidy renamed, which "
                                       f"is a change of what it tests:\n"
                                       + "\n".join(m for st, _c, m in built.entries if st == "fail")[-600:])
            return
        probe = Result()
        check_test_state(probe, profile, copy, table, "red", {s: located[s] for s in moved})
    proved = []
    for selector in moved:
        seen = [(st, m) for st, c, m in probe.entries if c == "tests-red" and selector in m]
        verdict, _said = break_verdict(seen)
        timed_out = any(st == "note" for st, _m in seen)
        if verdict == "red" and not timed_out:
            proved.append(selector)
            result.ok("red-reproof", f"{selector}: changed by tidy, red again on the tree the test stage left")
        elif verdict == "red":
            result.fail("red-reproof", f"{selector}: changed by tidy, and red on the test stage's tree only on a "
                                       f"timeout — an action waited, no assertion failed, so the moved test proves "
                                       f"nothing yet")
        elif verdict == "green":
            result.fail("red-reproof", f"{selector}: changed by tidy, and green on the tree the test stage left — the "
                                       f"move changed what it asserts; put it back, a change of what it expects is a "
                                       f"human's decision")
        else:
            result.fail("red-reproof", f"{selector}: changed by tidy, and no run on the test stage's tree gave it a "
                                       f"verdict — {_said}")
    if proved:
        digests = read_red_digests(runs, story_id)
        write_red_ledger(runs, story_id, set(proved), located, cwd,
                         kept={s: d for s, d in digests.items() if s not in proved})
        for selector in proved:
            with contextlib.suppress(OSError):
                journal_append(runs, story_id, "red-reproved", selector, "by=tidy")


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
CHANGE_CHECKS = ("compile", "test", "architecture", "format")


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
    # Nor is what the pipeline writes itself while a runner works — `.dca-factory/`, the run folder and
    # the evidence beside it: a person's commit is not refused by a running factory's protocol.
    tooling = lambda p: any(folder in "/" + p for folder in TOOL_FOLDERS)
    owned = pipeline_owned()
    left = [p for p in unstaged.splitlines() + untracked.splitlines() if p and owned(p)]
    drift = [f"modified, not staged: {p}" for p in unstaged.splitlines() if p and not tooling(p) and not owned(p)] \
        + [f"untracked: {p}" for p in untracked.splitlines() if p and not tooling(p) and not owned(p)]
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
    result.ok("snapshot", f"index tree {tree[:12]} — the working tree matches it"
                          + (f" ({len(left)} file(s) the pipeline writes itself left out)" if left else ""))
    return tree


def pipeline_owned():
    """Whether a path is one the pipeline writes itself, outside any story's commit: under `.dca-factory/`, the
    run folder or the evidence beside it, as the profile places them."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).strip("/")
    prefixes = tuple(dict.fromkeys(folder + "/" for folder in (".dca-factory", runs, evidence_rel()) if folder))
    return lambda path: path.replace("\\", "/").startswith(prefixes)


def backlog_places():
    """The backlog and the description — what a person writes and nothing the project's checks read: the epics with
    their stories, decisions and findings, the project's findings and decision records, the discovery and the
    description's files. Never the spec, never `docs/` (a project's tests may read what it holds). (folders, files)"""
    rel = lambda key: (PLACES_REL.get(key) or DEFAULTS[key]).strip("/")
    folders = {rel("epics"), findings_rel(), project_decisions_rel(), rel("discovery")}
    return (tuple(sorted(f.strip("/") + "/" for f in folders if f and f.strip("/") not in ("", "."))),
            {rel("product"), rel("tech"), rel("domain")})


def people_places():
    """What a request may write and the factory commits: the backlog and the description (`backlog_places`), and
    beside them the folder the epics lie in with everything in it, `docs/` and the agents' instructions a
    description writes a line into. Never the spec: what holds is merged by the gate that delivers.
    (folders, files, never)"""
    rel = lambda key: (PLACES_REL.get(key) or DEFAULTS[key]).strip("/")
    folders, files = backlog_places()
    more = {os.path.dirname(rel("epics")) or rel("epics"), "docs"}
    return (tuple(sorted(set(folders) | {f.strip("/") + "/" for f in more if f.strip("/") not in ("", ".")})),
            files | {"AGENTS.md", "CLAUDE.md"}, (rel("spec") + "/",))


def in_places(path, places):
    """Whether a path lies in (folders, files[, never])."""
    path = path.replace("\\", "/")
    folders, files, never = (tuple(places) + ((),))[:3]
    return (path in files or path.startswith(folders)) and not (never and path.startswith(never))


def backlog_paths(cwd, env):
    """The staged paths when every one of them is the backlog or the description (`backlog_places`) or the pipeline's
    own protocol, else None. A commit that stages nothing is None: it is checked as any other."""
    code, names = git(cwd, "diff", "--cached", "--name-only", "--no-renames", env=env)
    paths = [p for p in names.splitlines() if p] if code == 0 else []
    if not paths:
        return None
    owned, places = pipeline_owned(), backlog_places()
    return paths if all(in_places(p, places) or owned(p) for p in paths) else None


def red(result, check, message, must, strict):
    """A red check fails the verdict — unless a policy is declared and this check is not in it.
    Then the policy decides: the red run is reported, and it is not what the commit is judged by."""
    if strict and not must:
        result.note(check, message + " — optional (not in `required:`), so it does not decide")
    else:
        result.fail(check, message)


def run_test_command(result, cwd, profile, key, command, required, strict=False, owner=None):
    """A test command passes only when its reports show it executed tests and none failed. With `owner` (a story's
    whole suite) a red test outside the story runs again alone once (`retry_outside`)."""
    code, output, ran, reused = recorded_run(command, cwd, profile, with_reports=True)
    code, ran = retry_outside(result, cwd, profile, command, code, output, ran, owner)
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


#: WP-113: a whole suite red in a test the story did not write, change or name is run again for that test alone, once.
#: Green alone, the red was the suite's load or order, not this story: the gate passes with `flaky <test>` noted. More
#: red tests than this outside the story is a broken suite, not a flake — nothing is run again.
FLAKY_LIMIT = 3


class SuiteOwner(typing.NamedTuple):
    """Whose change a whole suite run judges: the story's run folder, id and criterion-to-test table."""
    runs: str
    story_id: str
    mapping: dict


def story_test_files(cwd, owner):
    """The test files the story wrote or changed — not in its baseline, or another blob than there — or None without a
    baseline: then which tests are the story's cannot be told, and none is run again."""
    path = os.path.join(evidence_dir(owner.runs, owner.story_id), TESTS_BASELINE)
    if not os.path.isfile(path):
        return None
    before = {}
    for line in read_text(path).splitlines():
        if "  " in line:
            blob, rel = line.split("  ", 1)
            before[rel] = blob
    files = test_files(cwd)
    if not files:
        return []
    try:
        completed = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=cwd, input="\n".join(files) + "\n",
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    blobs = completed.stdout.split()
    if completed.returncode or len(blobs) != len(files):
        return None
    return [rel for rel, blob in zip(files, blobs) if before.get(rel) != blob]


def story_owns(cwd, owner, own_files, cls, method):
    """Whether a reported test is the story's: named in its table, or a class of a test file it wrote or changed —
    by the file's name or by a declaration in it. When in doubt it is the story's: its red proof must stay exact."""
    for selectors in (owner.mapping or {}).values():
        for selector in selectors:
            match = SELECTOR.match(selector)
            if match and match.group(2) == method and (
                    match.group(1) == cls or cls.endswith("." + match.group(1)) or match.group(1).endswith("." + cls)):
                return True
    names = [n for n in re.split(r"[.$+/:]", cls) if n][-2:]
    for rel in own_files:
        stem = os.path.splitext(os.path.basename(rel))[0]
        if stem in names:
            return True
        text = read_text(os.path.join(cwd, rel)) if os.path.isfile(os.path.join(cwd, rel)) else ""
        if names and re.search(rf"\b{re.escape(names[-1])}\b", text):
            return True
    return False


def alone_invocation(cwd, profile, command, cls, method):
    """The profile's way to run one test of `command` — `<command> <filterFlag> "<filterFormat>"` — or None where the
    profile names none (no filter, or the exit code as the only evidence): then nothing is run again."""
    if str(profile.get("testEvidence", "")).strip() == "exit-code":
        return None
    flag, fmt = profile.get("filterFlag", ""), profile.get("filterFormat", "")
    if not flag and not fmt:
        return None
    fmt = fmt or "{class}.{method}"
    test_path = None
    if "{file}" in fmt:
        located = locate_selector(cwd, f"{cls}#{method}") if SELECTOR.match(f"{cls}#{method}") else None
        if not located:
            return None
        test_path = os.path.relpath(located, cwd).replace(os.sep, "/")
    return f'{command} {flag} "{fill(fmt, cls, method, test_path)}"'.strip()


def retry_outside(result, cwd, profile, command, code, output, ran, owner):
    """(code, ran) after the red tests outside the story ran again, each alone and once (WP-113).

    Only when every red test is outside the story and the profile can select one: a red test of the story's own stands
    as it is. Green alone, the test is noted `flaky` — the report, the journal (`flaky=`) and the status carry it — and
    the run counts as green; red again, the run stays red and the report names the test as outside the story."""
    if owner is None:
        return code, ran
    failed = sorted(key for key, outcome in ran.items() if outcome == "failed")
    if not failed or len(failed) > FLAKY_LIMIT:
        return code, ran
    own_files = story_test_files(cwd, owner)
    if own_files is None or any(story_owns(cwd, owner, own_files, cls, method) for cls, method in failed):
        return code, ran
    flaky, still = [], []
    for cls, method in failed:
        alone = alone_invocation(cwd, profile, command, cls, method)
        if not alone:
            return code, ran
        _code, _output, ran_alone, _reused = recorded_run(alone, cwd, profile, with_reports=True)
        outcome, _how = outcome_for(ran_alone, cls, method)
        (flaky if outcome == "passed" else still).append((cls, method, alone))
    if still:
        result.note("suite", f"{', '.join(f'{c}#{m}' for c, m, _a in still)} — outside this story's change (not "
                             f"written, changed or named in its table), red again on its own run "
                             f"(`{still[0][2]}`): the suite is red, not this story's code alone")
        return code, ran
    ran = dict(ran)
    for cls, method, alone in flaky:
        ran[(cls, method)] = "passed"
        result.flaky.append(f"{cls}#{method}")
        result.note("flaky", f"flaky {cls}#{method} — red in `{command}`, green on its own run (`{alone}`); a test "
                             f"this story did not write, change or name, so no round is counted")
    return 0, ran


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


def tree_tests(cwd, tree):
    """{test file: blob} of a tree object, relative to the project as `test_files` finds them; None without one."""
    if not tree or tree == "none":
        return None
    code, out = git(cwd, "ls-tree", "-r", "-z", tree)
    if code:
        return None
    skipped = SKIP_DIRS | {runs_top()}
    found = {}
    for entry in out.split("\0"):
        meta, _, rel = entry.partition("\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob" or not TEST_FILE.search(os.path.basename(rel)):
            continue
        if any(d in skipped or d.startswith(".") for d in rel.split("/")[:-1]):
            continue
        found[rel] = parts[2]
    return found


def rebase_tests_baseline(cwd, runs, story_id, new, old=None):
    """After the runner brought the main line into a story's branch: "existed before this story" is the main line
    as it was merged. Every test in the main line's tree `new` is held to the main line's version, so a test the
    main line changed while the story waited is not the story's change; one the main line removed leaves the
    baseline (where `old`, the base before, says it was tracked). `new` is the main line's tree, never the story's
    branch — nothing the story changed, committed by the runner before the merge or not, gets into the baseline."""
    path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
    main = tree_tests(cwd, new)
    if not os.path.isfile(path) or main is None:
        return
    before = tree_tests(cwd, old) or {}
    entries = {}
    for line in read_text(path).splitlines():
        if "  " in line:
            blob, rel = line.split("  ", 1)
            entries[rel] = blob
    rebased = {rel: blob for rel, blob in entries.items() if rel in main or rel not in before}
    rebased.update(main)
    if rebased != entries:
        write_mark(runs, story_id, TESTS_BASELINE, "\n".join(f"{blob}  {rel}" for rel, blob in sorted(rebased.items())))


#: The main line's side of the tests a merge met (#151): written when merging the main line into a story stops on a
#: conflict — every test file the main line changed since the story's base, as `<base blob | ->\t<main blob>\t<file>`
#: — so the integrate gate tells a resolution that dropped what the main line added to a test from the story's own
#: change, and the runner sends it back to the integrate stage.
MAIN_TESTS = "main-tests"


def record_main_tests(cwd, runs, story_id, target):
    """During a merge that stopped on conflicts in the story's worktree (`HEAD` the story, `target` the main line):
    the test files the main line changed since the two parted, with both versions. Nothing to hold, no record."""
    base = git(cwd, "merge-base", "HEAD", target)[1].strip()
    before, main = tree_tests(cwd, base) or {}, tree_tests(cwd, target) or {}
    rows = [f"{before.get(rel, '-')}\t{blob}\t{rel}" for rel, blob in sorted(main.items()) if before.get(rel) != blob]
    path = os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)
    if rows:
        write_mark(runs, story_id, MAIN_TESTS, "\n".join(rows))
    elif os.path.isfile(path):
        os.remove(path)


def main_tests_lost(cwd, runs, story_id, waive=True):
    """[(test file, [line, …])]: what the main line added to a test while the story ran that the story's tree no
    longer holds — a case another story added, an assertion it changed. Lines the main line kept from the base are
    the story's to change (and `tests-kept` holds the story to them); the main line's own lines are not. A file an
    answered integrate decision names is the person's to settle (`waive`, #163): it is left out."""
    lost = _main_tests_lost(cwd, runs, story_id)
    return [(rel, lines) for rel, lines in lost if not main_tests_waiver(cwd, story_id, rel)] if waive else lost


def main_tests_adapted(cwd, runs, story_id):
    """[(test file, [line, …])]: the main line's test lines the merge rewrote to a name the story re-signed (#163)."""
    adapted = []
    _main_tests_lost(cwd, runs, story_id, adapted)
    return adapted


def main_tests_waiver(cwd, story_id, rel):
    """The ids of the story's answered integrate decisions that name this test file — by its path or its file name, as
    a record names it — a person answered how its
    main-line lines are resolved, so the check holds the resolution to that answer, not to the lines (#163). Read in
    the main checkout, where the records are: the integrate step has taken the worktree's links down."""
    try:
        records = records_of(story_id, cwd=factory_home() or cwd)
    except (GateError, OSError):
        return []
    return [str(front.get("id", "")).strip() for _p, front, body, state, _a in records
            if state in ("answered", "applied") and str(front.get("stage", "")).strip() == "integrate"
            and (rel in body or re.search(rf"(?<![\w./-]){re.escape(os.path.basename(rel))}(?![\w.-])", body))]


#: A name called or declared on a line: `Name(`, `obj.Name(`, `new Name(` — the words before a parenthesis that are no
#: statement of the language.
CALLED = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^<>()]*>)?\s*\(")
NOT_CALLS = {"if", "for", "foreach", "while", "switch", "catch", "return", "new", "typeof", "nameof", "sizeof", "lock",
             "using", "fixed", "base", "this", "super", "await", "throw", "when", "assert", "synchronized", "with"}


#: A name declared on a line: a word — a type, a modifier, `def`, `record` — then the name and its parameters
#: (`public Money Total(`, `record Command(`, `def total(`); never `.Name(`, `= Name(`, `return Name(`, `new Name(`.
DECLARED = re.compile(r"(?:^|\s)([A-Za-z_][\w.<>\[\],?]*[\w>\]?]|>)\s+([A-Za-z_]\w*)\s*(?:<[^<>()]*>)?\s*\(")
NOT_DECLARING = {"return", "new", "await", "throw", "yield", "else", "case", "in", "is", "as", "and", "or", "not",
                 "await", "typeof", "nameof", "var", "val", "let"}


def called_names(line):
    return {name for name in CALLED.findall(line) if name not in NOT_CALLS}


def declared_names(line):
    return {name for before, name in DECLARED.findall(line)
            if before.split(".")[-1] not in NOT_DECLARING and name not in NOT_CALLS}


def rewritten(line, lines):
    """Whether the file still has `line` in another form — a line alike to at least 60 % — so a missing line is not
    a case that went whole."""
    for other in lines:
        matcher = difflib.SequenceMatcher(None, line, other, autojunk=False)
        if matcher.real_quick_ratio() >= 0.6 and matcher.quick_ratio() >= 0.6 and matcher.ratio() >= 0.6:
            return True
    return False


def resigned_names(cwd, target):
    """The names the story's own change in production code re-signed or removed: every name declared on a line of a
    non-test file the story's tree no longer has as `target` (the main line) has it. A main-line test line that calls
    one of them was adapted to the story's new signature, or could not compile — not lost (#163)."""
    code, diff = git(cwd, "diff", "--no-color", "--unified=0", target, "--")
    if code:
        return set()
    names, test = set(), False
    for line in diff.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            rel = line[4:].strip()
            if rel != "/dev/null":
                test = bool(TEST_FILE.search(os.path.basename(rel[2:] if rel[:2] in ("a/", "b/") else rel)))
            continue
        if line[:1] == "-" and not test:
            names |= declared_names(line[1:])
    return names


def _main_tests_lost(cwd, runs, story_id, adapted=None):
    """The main line's added test lines the story's tree lacks. A missing line that calls a name the story's own
    production change re-signed or removed is the merge adapting another story's helper to it — collected in
    `adapted`, not lost; a test case's own lines (its head, its attributes) name no such name and stay asked for."""
    path = os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)
    if not os.path.isfile(path):
        return []
    lost, resigned = [], None
    for line in read_text(path).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        before_blob, main_blob, rel = parts
        code, main_text = git_blob(cwd, main_blob)
        if code:
            continue
        base_text = "" if before_blob == "-" else git_blob(cwd, before_blob)[1]
        # compared without their indentation: a resolution may indent a case anew
        was = [l.strip() for l in meaningful_lines(base_text, rel)]
        main = [l.strip() for l in meaningful_lines(main_text, rel)]
        added = [main[j] for tag, _i1, _i2, j1, j2 in
                 difflib.SequenceMatcher(None, was, main, autojunk=False).get_opcodes()
                 if tag in ("insert", "replace") for j in range(j1, j2)]
        full = os.path.join(cwd, rel)
        if not os.path.isfile(full):
            lost.append((rel, ["(the file is gone)"]))
            continue
        with open(full, encoding="utf-8", errors="replace") as handle:
            now = [l.strip() for l in meaningful_lines(handle.read(), rel)]
        left = collections.Counter(now)
        missing = []
        for wanted in added:
            if left[wanted] > 0:
                left[wanted] -= 1
            else:
                missing.append(wanted)
        if missing:
            if resigned is None:
                target = merge_target(runs, story_id, cwd)
                resigned = resigned_names(cwd, target) if target else set()
            kept = [line for line in missing if called_names(line) & resigned and rewritten(line, now)]
            if kept and adapted is not None:
                adapted.append((rel, kept))
            missing = [line for line in missing if line not in kept]
        if missing:
            lost.append((rel, missing))
    return lost


def lost_text(lost):
    """The lost lines as a reader takes them in: each file with its first lines."""
    return "; ".join(f"{rel} lost {', '.join(repr(l) for l in lines[:2])}"
                     + (f" and {len(lines) - 2} more line(s)" if len(lines) > 2 else "") for rel, lines in lost)


def check_main_tests(result, cwd, runs, story_id):
    """#151: the merge's resolution keeps the main line's side of every test it met. A line the main line added to a
    test while the story ran — another story's case — that the story's tree lacks is the resolution's change, never
    the story's: refused here by name, and the runner sends it back to the integrate stage."""
    if not os.path.isfile(os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)):
        return
    lost = main_tests_lost(cwd, runs, story_id)
    target = integration_target(runs, story_id) or "the main line"
    for rel, lines in main_tests_adapted(cwd, runs, story_id):
        result.note("main-tests", f"{rel}: {len(lines)} line(s) of the main line call what the story re-signed — taken as "
                                  f"adapted, not asked back: {', '.join(repr(l) for l in lines[:2])}"
                                  + (" …" if len(lines) > 2 else ""))
    for rel, _lines in main_tests_lost(cwd, runs, story_id, waive=False):
        ids = main_tests_waiver(cwd, story_id, rel)
        if ids:
            result.note("main-tests", f"{rel} keeps the resolution {', '.join(ids)} answered — the main line's lines "
                                      f"there are not asked back")
    if lost:
        result.fail("main-tests", f"the merge's resolution changed a test the main line holds: {lost_text(lost)} — the "
                                  f"integrate stage puts the main line's side back (`git show {target}:<file>`) beside "
                                  f"the story's")
    else:
        result.ok("main-tests", "every test the main line changed while the story ran keeps the main line's side")


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
    """The tests that existed before the story still expect what they did (`KeptChecks.tests_kept`)."""
    story = stage_story(story_id, "", {}, story_body, ())
    take(result, KeptChecks.tests_kept(story, StageEvidenceFiles(cwd, runs, place("epics"), {})))


def check_required_suites(result, profile, cwd, already=None, owner=None):
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
            code, ran = retry_outside(result, cwd, profile, profile[key], code, output, ran, owner)
            judge_test_run(result, profile, key, profile[key], code, output, ran, True, True,
                           reused=" (the run the mapped tests were read from)")
        else:
            run_test_command(result, cwd, profile, key, profile[key], True, True, owner=owner)
        result.entries[before:] = [(state, "suite" if check != "flaky" else check, message)
                                   for state, check, message in result.entries[before:]]


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
    paths = backlog_paths(cwd, env) if staged and not split_list(only) else None
    if staged:
        if paths and not split_list(profile.get("checks.backlog")):
            # nothing runs over the working tree: what else is changed there cannot reach a check of this commit
            result.note("snapshot", "the backlog alone, and `checks.backlog` names no check — what else the working "
                                    "tree holds is not this commit's")
        else:
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
    # A commit of the backlog alone — stories, decisions, findings, the pipeline's protocol — changes no code: it
    # runs what `checks.backlog` names (a project whose tests read the backlog names them), by each check's or
    # test command's own key, and nothing more. An explicit `--checks` scope is the person's and wins.
    test_scope = None
    if paths:
        named = split_list(profile.get("checks.backlog"))
        unknown = sorted(n for n in named if n not in CHANGE_CHECKS and n not in test_keys)
        if unknown:
            result.fail("policy", f"`checks.backlog:` names {', '.join(unknown)} — it takes compile, architecture, "
                                  f"format and the profile's test-command keys (test, e2eTest, test.<name>)")
        test_scope = {n for n in named if n in test_keys}
        scope = [n for n in named if n in CHANGE_CHECKS and n != "test"] + (["test"] if test_scope else [])
        result.note("scope", f"the commit changes only the backlog and the pipeline's own files "
                             f"({len(paths)} path(s)) — `checks.backlog` runs "
                             + (", ".join(named) if named else "no check"))
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
                if test_scope is not None and key not in test_scope:
                    result.skip(key, "not run in this scope" + (" — it is required, so a later scope (CI) has "
                                                                "to run it" if key in required else ""))
                    continue
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
    if tree:
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
        self.written = []          # the files a delivery wrote into the project — what integrate commits on main
        self.flaky = []            # the tests outside the story red in a whole run and green alone (WP-113)
        self.closed = False        # a delivery journaled its passing verdict before its commit (close_record)

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
        self.evidence = StageEvidenceFiles(self.cwd, self.runs, self.args.epics, self.profile)
        self.story = stage_story(self.story_id, self.story_path, self.front, self.body, self.criteria)
        self.contract = ProfileChecks.contract_number(self.evidence)
        # a journey is a guard over what is delivered: green at its test gate, the inverse of a story
        self.expected = "red" if self.stage.red and self.kind == "story" else "green"


class Check(typing.NamedTuple):
    name: str
    run: typing.Callable
    stages: tuple
    needs_process: bool
    unrun: typing.Callable       #: the check names a refusal before it leaves unproven
    kinds: tuple                 #: the story kinds it holds (a task has no criteria, so none of their checks)


#: The checks a gate run holds a story to, in this order: every check that needs no process first, and a refusal among
#: them ends the run before a suite starts — a file list that is wrong is wrong in a millisecond, not after a minute of
#: tests. What did not run is named, so the report says what is still unproven.
CHECKS = []


def check(name, stages=None, needs_process=False, unrun=None, kinds=ALL_KINDS):
    """Register a check against the stage table: `stages` names rows (None — every gated stage) or is a predicate
    over a row; `kinds` the story kinds it holds."""
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
        CHECKS.append(Check(name, function, chosen, needs_process, unrun or (lambda run: [name]), tuple(kinds)))
        return function
    return register


def run_checks(run):
    chosen = [c for c in CHECKS if run.stage.name in c.stages and run.kind in c.kinds]
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
    take(run.result, StoryChecks.context(run.story))


@check("contract")
def _contract(run):
    take(run.result, ProfileChecks.contract(run.evidence))


@check("status")
def _status(run):
    take(run.result, StoryChecks.status(run.story))


@check("epic")
def _epic(run):
    take(run.result, BacklogChecks.epic(run.story, run.evidence))


@check("outcome", stages=("plan",), kinds=TESTED_KINDS)
def _outcome_named(run):
    take(run.result, BacklogChecks.outcome(run.story, run.contract, run.evidence))


@check("rounds")
def _rounds(run):
    take(run.result, StoryChecks.rounds(run.story, run.evidence))


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
    take(run.result, StoryChecks.owned(run.story, run.evidence))


@check("adopt", stages=("adopt",))
def _adopt(run):
    check_adopt(run.result, run.profile, run.cwd, run.runs, run.story_id, run.front, run.criteria)


@check("integrate", stages=("integrate",))
def _integrated(run):
    check_integrated(run.result, run.cwd, run.runs, run.story_id)
    check_main_tests(run.result, run.cwd, run.runs, run.story_id)
    # The spec as the main line holds it now: a key another story added meanwhile, or a criterion it changed, is a
    # question to a person — never a silent last-writer-wins (WP-98 R3). With claims on a remote the main line is the
    # remote's, merged into this worktree (WP-93 D).
    if claim_config_here(factory_home() or run.cwd):
        with places_in(run.cwd):
            check_spec_delta(run.result, run.cwd, run.runs, run.story_id, run.story_path, run.front, run.body)
    else:
        check_spec_delta(run.result, run.cwd, run.runs, run.story_id, run.story_path, run.front, run.body)


@check("tests-mapped", stages=lambda s: s.tested, kinds=TESTED_KINDS)
def _mapping(run):
    run.mapping = check_mapping(run.result, run.runs, run.story_id, run.criteria)
    run.located = check_exists(run.result, run.cwd, run.mapping)


# Integrated, the story's diff carries the main line's changes beside its own: the file list, the tests that existed
# before and the red proof were the stages' to hold, and they held.
@check("files-listed", stages=lambda s: s.lists)
def _files_listed(run):
    take(run.result, KeptChecks.files_listed(run.story, StageName(run.stage.name), mapped_tests(run), run.evidence))
    take(run.result, KeptChecks.tests_kept(run.story, run.evidence))


@check("test-design", stages=lambda s: s.red)
def _test_design(run):
    take(run.result, TestChecks.plan_levels(run.story, run.evidence))
    tests = mapped_tests(run)
    take(run.result, DesignChecks.invariants(run.story, run.contract, tests, run.evidence))
    take(run.result, TestChecks.levels(run.story, run.contract, tests, run.evidence))
    take(run.result, DesignChecks.clauses(run.story, run.contract, tests, run.evidence))
    take(run.result, TestChecks.titles(run.story, run.contract, tests, run.evidence))


@check("spec-delta", stages=("test",))
def _spec_delta(run):
    check_spec_delta(run.result, run.cwd, run.runs, run.story_id, run.story_path, run.front, run.body)


@check("spec-tests", stages=("document", "adopt", "integrate"), kinds=TESTED_KINDS)
def _spec_tests(run):
    check_spec_tests(run.result, run.cwd, run.runs, run.story_id, run.front, run.mapping)


@check("tests-committed", stages=("integrate",), kinds=TESTED_KINDS)
def _tests_committed(run):
    check_tests_committed(run.result, run.cwd, run.front, run.mapping)


@check("tests-real", stages=("test", "adopt"))
def _tests_real(run):
    if contract_of(run.profile) >= 21:
        take(run.result, DesignChecks.tests_real(run.story, mapped_tests(run), run.evidence))


@check("plan-files", stages=("build",))
def _plan_files(run):
    if contract_of(run.profile) >= 22:
        take(run.result, DesignChecks.plan_files(run.story, run.evidence))


@check("size", stages=lambda s: s.sizes)
def _size(run):
    take(run.result, TestChecks.size(run.story, tuple(HandOverName(name) for name in run.stage.sizes), run.evidence))


@check("red-proof", stages=lambda s: s.lists, kinds=TESTED_KINDS)
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


@check("tests", stages=lambda s: s.tested, needs_process=True,
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


@check("invariant-breaks", stages=("test",), needs_process=True, kinds=("story",))
def _invariant_breaks(run):
    if contract_of(run.profile) >= 25:
        check_invariant_breaks(run.result, run.profile, run.cwd, run.runs, run.story_id, run.mapping)


@check("red-reproof", stages=("tidy",), needs_process=True, kinds=("story",))
def _red_reproof(run):
    reprove_red(run.result, run.profile, run.cwd, run.runs, run.story_id, run.mapping, run.located)


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
                others.setdefault(test, []).append(other)
    open_rows = set()
    with contextlib.suppress(GateError, OSError):
        open_rows = {(where, perspective) for _s, where, _sev, _d, perspective, _f, _p in open_findings(place("epics"))}
    added = []
    for test in sorted(mine):
        if test not in others or (test, "flaky") in open_rows:
            continue
        seen = ", ".join([story_id] + others[test])
        added.append(("flaky", test, "minor", f"red in a whole suite run and green on its own run, in {seen}",
                      "find what it depends on — load, order, a timeout, shared state — and fix the test or the "
                      "code, as a task", f"The test {test} fails now and then in the whole suite, in more than one "
                                         f"story — it is fixed, not run again"))
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


def merge_target(runs, story_id, cwd=None):
    """What a story integrates against: the main checkout's branch — or, where the profile claims stories on a remote
    (WP-93), that branch as the remote has it, fetched: the main line every factory shares."""
    target = integration_target(runs, story_id)
    config = claim_config_here(factory_home() or cwd)
    return remote_main(config["remote"], target) if config and target else target


def check_integrated(result, cwd, runs, story_id):
    """The story's branch carries the main line and nothing half-merged: no unmerged path, no conflict marker in
    a file the story's commit changes, and its commit sits on the target's tip — a target that moved since is
    integrated again (`moved`), not refused."""
    if not in_worktree(cwd):
        result.fail("integrate", f"the integrate gate runs in the story's worktree, with {HOME_VARIABLE} naming the "
                                 f"main checkout — the runner's integrate step starts it")
        return
    if not integration_target(runs, story_id):
        result.fail("integrate", f"no target recorded for {story_id} (<evidence>/<story>/target) — the worktree was not made "
                                 f"by the runner")
        return
    target = merge_target(runs, story_id, cwd)
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


def spec_target(front):
    """The spec file a story changes: its feature's `scenarios.md` under its context — the context's own for a story
    without `feature:` —, or `journeys.md` for a journey item; None for a story that names no context."""
    if story_kind(front) == "journey":
        return journeys_path()
    return scenarios_path(front["context"], front.get("feature")) if str(front.get("context", "")).strip() else None


def story_spec(front):
    """(the file the story's criteria go to, what the spec holds where the story's keys are looked up — every
    criterion of the context with its feature —, the context's features, the story's feature). A journey's is
    `journeys.md` alone."""
    target = spec_target(front)
    if not target:
        return None, [], set(), ""
    if story_kind(front) == "journey":
        return target, [dict(item, feature="") for item in read_spec(target)[1]], set(), ""
    context = front["context"]
    return (target, read_context(context), {name for name, _p in context_files(context) if name},
            feature_name(front.get("feature")))


def spec_backing(cwd, story_id, body, story_path=None):
    """What backs a change of what holds: the story's `## Changed expectations` in a person's words, or a decision a
    human answered for this story. "" where nothing does."""
    if any(l.strip().startswith(("-", "*")) and human_line(l.strip()[1:].strip())
           for l in section_of(body, "changed expectations") or []):
        return "the story's `## Changed expectations`"
    try:
        answered = [str(f["id"]).strip() for _p, f, _b, state, a in records_of(story_id, story_path)
                    if state in ("answered", "applied") and not (is_acceptance(f) and accepted(a))]
    except GateError:
        answered = []
    return f"decision {', '.join(answered)}" if answered else ""


def check_spec_delta(result, cwd, runs, story_id, story_path, front, body):
    """WP-98: the plan's `## Spec delta` against the story and the spec as it stands. What follows from comparing them
    the gate derives; what the plan names must agree with it, a removal must name a criterion the spec holds, a
    renamed rule must leave nothing under its old text, and every change or removal of what holds needs a person's
    sentence behind it — the plan stage asks where there is none."""
    plan_path = os.path.join(runs, story_id, "plan.md")
    if not os.path.isfile(plan_path):
        return
    target, spec, features, feature = story_spec(front)
    if not target:
        return
    story = story_entries(body)
    delta = read_delta(read_text(plan_path))
    problems = delta_problems(story, spec, delta) \
        + rule_problems(section_of(body, "changed expectations") or [], story, spec, delta)
    if story_kind(front) != "journey":
        problems += placement_problems(story, spec, delta, feature, features)
    if problems:
        result.fail("spec-delta", f"{shown(plan_path)} `## Spec delta` against {shown(target)}: " + "; ".join(problems))
        return
    touched = touches(story, spec, delta)
    if touched:
        backing = spec_backing(cwd, story_id, body, story_path)
        if not backing:
            result.fail("spec-delta", f"the story changes or removes what holds ({', '.join(touched)} in {shown(target)}) "
                                      f"and no person said so — no `## Changed expectations` in the story, no answered "
                                      f"decision. The plan stage asks (one record naming the keys); the answer backs it.")
            return
        result.ok("spec-delta", f"{', '.join(touched)} changed or removed in {shown(target)}, backed by {backing}")
        return
    found = derived(story, spec)
    result.ok("spec-delta", f"{sum(v == 'adds' for v in found.values())} added, {sum(v == 'holds' for v in found.values())} "
                            f"held in {shown(target)} — nothing that holds changes")


def moved_tests(runs, story_id):
    """{key: [selector]} from tests.md's `## Moved tests` table — a test of the spec this story renamed or moved."""
    path = os.path.join(runs, story_id, "tests.md")
    moved = {}
    for line in (section_of(read_text(path), "moved tests") or []) if os.path.isfile(path) else []:
        row = MAPPING_ROW.match(line.strip())
        if row and row.group(1) not in ("criterion", "key", "---") and SELECTOR.match(row.group(2).strip()):
            moved.setdefault(row.group(1), []).append(row.group(2).strip())
    return moved


def check_spec_tests(result, cwd, runs, story_id, front, mapping):
    """WP-98 M3: every `Test:` line of the spec the story changes still names a test that is there — one this story
    renamed or moved is named under tests.md's `## Moved tests` (or is the story's own criterion), and the gate
    writes the new selector at delivery."""
    target, spec, _features, _feature = story_spec(front)
    if not target:
        return
    plan = os.path.join(runs, story_id, "plan.md")
    # a criterion the story takes away takes its test with it (WP-106 B): the delta's removals are not asked for
    removed = set(read_delta(read_text(plan))["removes"]) if os.path.isfile(plan) else set()
    moved = moved_tests(runs, story_id)
    if moved:
        # a row names the test as it is now: the old one is gone, and the delivery writes the row into the spec
        probe = Result()
        check_exists(probe, cwd, moved)
        absent = [message.split(" — ")[0] for state, _c, message in probe.entries if state == "fail"]
        if absent:
            result.fail("spec-tests", f"tests.md's `## Moved tests` names a test that is not there: {'; '.join(absent)}"
                                      f" — a row names the test as it is now, not the one it replaced")
            return
    own = set(mapping or {}) | set(moved) | removed
    wanted = {item["key"]: item["tests"] for item in spec if item["tests"] and item["key"] not in own}
    if not wanted:
        return
    probe = Result()
    check_exists(probe, cwd, wanted)
    missing = [message.split(" — ")[0] for state, _c, message in probe.entries if state == "fail"]
    if missing and in_worktree(cwd):
        # The spec is the main checkout's; a story delivered there meanwhile names tests this worktree, branched
        # before it, does not have yet. They are not gone: the integrate gate checks again on the main line.
        there = Result()
        check_exists(there, factory_home(), wanted)
        gone_there = {message.split(":")[0] for state, _c, message in there.entries if state == "fail"}
        missing = [m for m in missing if m.split(":")[0] in gone_there]
    if missing:
        result.fail("spec-tests", f"{shown(target)} names a test that is gone: {'; '.join(missing)} — a test this story "
                                  f"renamed or moved goes under tests.md's `## Moved tests` (| <key> | <Class>#<method> |)")
    else:
        result.ok("spec-tests", f"every test line of {shown(target)} names a test that is there")


def check_tests_committed(result, cwd, front, mapping):
    """What the main line takes is the story's commit, not its worktree: every test the story maps, and every one a
    `Test:` line of its spec names, sits in a file that commit holds as the worktree has it. A file the story made and
    no record took in (untracked, ignored, changed after the squash) would pass every check here and be gone with
    the worktree — the spec then names a test the main line lacks."""
    target, spec, _features, _feature = story_spec(front)
    wanted = {key: list(selectors) for key, selectors in (mapping or {}).items()}
    for item in spec if target else []:
        if item["tests"]:
            wanted.setdefault(item["key"], [])
            wanted[item["key"]] += [t for t in item["tests"] if t not in wanted[item["key"]]]
    if not wanted:
        return
    probe = Result()
    located = check_exists(probe, cwd, wanted) or {}
    files = sorted(set(located.values()))
    if not files:
        return
    held = set(git(cwd, "ls-tree", "-r", "--name-only", "HEAD", "--", *files)[1].split("\n"))
    prefix = git(cwd, "rev-parse", "--show-prefix")[1].strip()
    # `git` strips its answer, so the first line's leading status column may be gone: the path is what follows the code
    dirty = {line.split(None, 1)[1].split(" -> ")[-1] for line in
             git(cwd, "status", "--porcelain", "--ignored", "--", *files)[1].split("\n") if len(line.split(None, 1)) == 2}
    head = git(cwd, "rev-parse", "--short", "HEAD")[1].strip()
    missing = []
    for rel in files:
        if rel not in held:
            selectors = sorted(s for s, path in located.items() if path == rel)
            missing.append(f"{rel} ({', '.join(selectors)}) is not in it")
        elif prefix + rel in dirty or rel in dirty:
            missing.append(f"{rel} differs from it")
    if missing:
        result.fail("tests-committed", f"the story's commit {head} lacks what its tests need: {'; '.join(missing)} — the "
                                       f"worktree has the file, the main line would not: a file the stages made goes into "
                                       f"the commit when a hand-over lists it (tests.md's `## Files`); an ignored one is "
                                       f"the person's to add (`git add -f`) or to un-ignore")
    else:
        result.ok("tests-committed", f"the story's commit {head} holds every test file its mapping and its spec name "
                                     f"({len(files)})")


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
    write_story_fields(story_path, status="delivered", delivered=stamp, delivered_by="gate")
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
