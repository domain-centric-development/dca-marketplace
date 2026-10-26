"""What a stage is told before it starts — its contract text and the skeleton of every hand-over file.

The gate's own shape per stage, said as `--contract` prints it, and the skeletons the runner writes before a stage:
plan, the files lists of the builder stages, the clauses and invariants tables and the document.
"""

from __future__ import annotations

import os
import sys
import typing
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .hand_over_patterns import MAPPING_ROW, SELECTOR
from ..pipeline.stage_rows import STAGE, STAGE_FILES, STAGE_ORDER
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, place, read_profile, resolve_profile
from .....spec.api import derived, placement_lines, story_entries
from ....domain.service.design_checks import CLAUSES_MARKER, INVARIANTS_MARKER
from ....domain.service.test_checks import HANDOVER_BUDGET
from .criteria_files import criteria_of
from ....application.profile.profile_rules import BUILT_IN_PERSPECTIVES
from .delivery_files import plan_proposals
from .design_files import plan_invariants, read_clause_rows, read_invariant_rows, scenario_clauses
from .decision_record_files import NOTHING
from .snapshots import git_tree, listed_files, snapshot_reason, tree_changes
from .stage_evidence_files import contract_of
from .story_layout import journeys_hold, find_story, story_kind
from ..spec.story_spec_files import story_spec


CONTRACT_HEAD = ("What the gate checks in this stage's file — the exact shape, from the gate's own code. A stage that "
                 "wants certainty reads this, not the gate.")


def contract_text(stage: str, runs: str) -> typing.Optional[str]:
    """The stage's contract, with the hand-over's measure appended: what the file has to say fits in a base plus a
    share per criterion (the gate notes a larger file, never refuses it)."""
    text = contract_body(stage, runs)
    if text is None:
        return None
    for name in (STAGE_FILES[stage],) if stage in STAGE_FILES else ():
        base, per = HANDOVER_BUDGET[name]
        text += (f"\n- size: what {name} has to say fits in {base / 1000:.1f} kB"
                 + (f" plus {per} bytes per criterion" if per else "")
                 + " — keys and levels, not the story's text; one citation per row; nothing a reader has elsewhere. "
                   "Larger is a `gate:note size`, never a refusal, and never a reason to edit the file after the gate "
                   "ran; a reason is one line"
                 + (" (the pipeline's `## Paths` does not count)" if name == "document.md" else ""))
    return text


def contract_body(stage: str, runs: str) -> typing.Optional[str]:
    """The shape the gate holds a stage's file to, in a page: the table columns, the selector form, the
    path rule, the section names — taken from the constants the checks read, so the two cannot drift apart
    without this text changing with them."""
    folder = f"{runs}/<story>"
    evidence = f"{evidence_dir(runs)}/<story>".replace(os.sep, "/")
    if stage == "plan":
        return f"""{CONTRACT_HEAD}

plan — {folder}/plan.md (gate before the stage: story, epic, context map, decisions, rounds; the test gate reads the plan)
- `## Acceptance criteria`: one line per criterion, the story's key verbatim and its level — not the story's text:
  `- <key>  →  level: e2e | integration | browser-only (<why>)`
  `factory-cli.py --plan-skeleton <story>` writes the file's headings and these lines with the keys: give each its level.
  The test gate reads `level: browser-only` here (`levels`); a key is `[a-z0-9][a-z0-9-]*`
- `## Invariants`: one line per aggregate, entity, value object or domain service `## Changes` names —
  `- <Element>: <rule>; <rule>` with its guards (required, trimmed, in range), or `- <Element>: none — <why>`.
  The test gate reads it (`invariants`): each named rule needs a unit test in tests.md's `## Notes`.
  An adopted story names the domain types its scenarios exercise instead, or `- none — <why>`: the line is required
- `## Spec delta`: the story against its context's spec (`product/spec/<context>/scenarios.md`) — the skeleton writes
  `- adds <key>` / `- holds <key>` / `- changes <key>` as the comparison says; add `- removes <key>: <why>` for a
  criterion the story takes away and `- rule "<old>" → "<new>"` for a renamed rule (the criteria under it follow it;
  a rule `## Changed expectations` quotes that the story no longer writes needs one). The test gate reads it (`spec-delta`): a change or removal of what holds needs the story's
  `## Changed expectations` or an answered decision — where neither says it, ask (`## needs-human`)
- `## Changed tests` (only when the story contradicts an existing test): `| <path from the project root> | <backing line or decision id> |`
- `## Files`: `- <path from the project root> — <changes|read>: <why>` (the path in backticks) — the next stages open these first
- `## Glossary proposals`: `- <term>: <definition>` — the document gate checks each term landed in a glossary or is named open
- `## needs-human` only to stop: `decision: <story>-<nn>`, with the record `<story>/decisions/<nn>.md` in the story's folder
  (`id:`, `story:`, `stage: plan`, `asked:`; `## Question`, `## Options`, `## Recommendation`)
- A citation is a path from the project root, `src/main/java/…/Thing.java:12`; a bare `Thing.java:12` resolves to nothing.
  A catalog node is cited by its path inside the catalog (`recipe/add-an-aggregate.md`), as the knowledge skill cites it —
  never by a path into a skill folder"""
    if stage == "test":
        return f"""{CONTRACT_HEAD}

test — {folder}/tests.md (gate after the stage: tests-mapped, tests-exist, compiles, tests-red, levels, test-titles, invariants, invariant-breaks, files-listed)
- the table, right after the marker `<!-- gate:tests -->`, one row per criterion (a criterion may have several rows):
  `| criterion | test |` then `| <key> | <selector> |`
  row pattern: {MAPPING_ROW.pattern!r}
- selector: `<fully.qualified.Class>#<method>` — pattern {SELECTOR.pattern!r}; the class resolves to a file named after it
  (`WidgetTest.java`), or to a module path (`tests.test_widgets#test_shows` → `tests/test_widgets.py`)
- levels: a test the profile's `e2eTest:` command runs belongs to the story's `(happy path)` scenario or to a key the
  plan gave `level: browser-only`; every other scenario's test lives in a `test.<name>:` source set
- titles: an end-user test's display name is the scenario's `Title:` line verbatim, else its key in words
  (`shows-empty-state` → "Shows empty state"); never the key itself in a name, display name or comment
- `## Moved tests` (a spec test the story renamed, of a key it does not carry): `| <key> | <new selector> |` (`spec-tests`)
- one process per test command; each selector is read from its report by name
- red: every selector in the table fails before any production code — the gate writes `{evidence}/.tests-red`
  (`<selector>\t<sha256 of the test file>`); the build gate refuses a test changed after it was seen red (`red-proof`)
- a round the judge sent back (`back: test`): a test you strengthen is already green and cannot be seen red — write its
  break, `{folder}/breaks/<fully.qualified.Class>--<method>.patch`, a `git apply` patch against the production code that
  turns it red; the gate applies it on a scratch copy (`break-proof`) and records the test's new version
- `## Files`: every test file this stage wrote or changed, one per line, as a path from the project root —
  `files-listed` compares it with the changed-files record; `factory-cli.py --files-skeleton <story> test`
  writes it from the tree, and the invariant rows below: run it, add the rest
- `## Invariants`: `<!-- gate:invariants -->`, a row per plan rule `| <Element> | <n> | <rule> | <Class>#<method> |`:
  each its own test, not a criterion's (`invariants`), a green one its break (`invariant-breaks`)
- `## Clauses` (contract 15): `<!-- gate:clauses -->`, per `Then`/`And` `| <key> | <n> | <clause> | <File>:<line> | <level> |`
  — the line asserting it, level `unit|port|adapter|e2e`; a stored-state clause never `adapter` (`clauses`)
- `## Notes`: `- uncovered: <key> — <why>` only when unavoidable — not what a test fails on: the red run records it
- stubs: a type with nothing a criterion observes (a record and its fields, an enum, an interface, an exception type) is
  written whole here; a method whose outcome a criterion asserts throws — whatever a criterion observes, throws"""
    if stage in FILES_SECTIONS and STAGE[stage].suite:
        table, name = ("## Changed", "build") if stage == "build" else ("## Moves", "tidy")
        return f"""{CONTRACT_HEAD}

{name} — {folder}/{STAGE_FILES[stage]} (gate after the stage: tests-green, red-proof{', red-reproof' if stage == 'tidy' else ''}, files-listed, existing tests, architecture, format)
- `{table}`: `| File | Why |` — the first cell is a path from the project root, in backticks or bare; the other cells
  are prose. `files-listed` refuses a file the pipeline recorded as changed that no row names; a listed file that did
  not change is a note. A stage that changed no file needs no such section (tidy) — say so and why.
  `factory-cli.py --files-skeleton <story> {stage}` writes the rows' first column from the tree (the file's
  skeleton, or the missing rows): run it when the changes are done, fill in the rest
- a test file put back to the version the test stage saw red is a restoration, not a change to list
- tests: every selector of the `gate:tests` table green, and its file's digest as `.tests-red` holds it (`red-proof`)
- {'`## Deviations from the plan`: `- <element>: <what differed and why>`, or nothing when the plan held. No `## Criteria` (the judge re-checks each one) and no `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run' if stage == 'build' else '`## Left alone`: what you saw and did not change, and why. No `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run'}
- `## needs-human` only to stop, with `decision: <story>-<nn>` and the record beside the story (`stage: {name}`)
- {'a test that cannot pass for a reason in its own code — a helper, a locator, a fixture — while what it asserts stays as it is: write `back: test` on a line of its own and say what is wrong; the round goes to the test stage, which repairs it and proves it with a break. A change to what a test asserts is still a question (`## needs-human`)' if stage == 'build' else 'the story\'s tests take moves that keep what each asserts — a copy lifted into the shared support, a page object instead of a raw locator, a name after its display name, a dead helper deleted —, each a row under `## Moves`; `red-reproof` runs every moved mapped test on the tree the test stage left and refuses one green there or not compiling. Never an assertion, an expected value, a selector or a scope: a defect in what a test asserts is a finding for the judge'}
- no criterion key in code, a comment or a test name; no `TODO` for the criterion delivered"""
    if stage == "judge":
        return f"""{CONTRACT_HEAD}

judge — {folder}/judge.md (the runner reads the verdict; the document gate reads `story-pass`)
- `## Verdict`: `verdict: pass | changes-requested | story-conflict` — one line, exactly one of the three
  (pass: deliverable; changes-requested: back one round; story-conflict: a human, never build)
- `back: test` under the verdict when a confirmed defect is in a test (it asserts less than its criterion): the round
  goes to the test stage, then build; without it the round goes to build, which may not change a test
- `## Perspectives covered`: `- <perspective>: reviews/<perspective>.md (<carrier>) | in-session — <why no file> | not covered — <why>`
- `## Confirmed defects`: `| Perspective | File:line | Severity | In plain words | Defect | Fix |` — file as a path from
  the project root with its line; severity blocker | major | minor; only blocker and major prevent `pass`; `In plain
  words` is one short sentence a person understands at once, no code name or line ("the checkout controller checks
  the step twice"), `Defect` the reviewer's precise account
- `## Considered and dropped`, `## Criteria re-checked`: `- <key>: met | met only nominally — <what the test does not assert>`
- `## Previous round` in a repeat round: every defect the previous verdict confirmed — fixed (file:line) | withdrawn (why) | still open
- a `story-conflict` names a decision record: `## needs-human` with `decision: <story>-<nn>`, the record's `stage:` is the one
  that applies the answer (plan or test)"""
    if stage == "document":
        return f"""{CONTRACT_HEAD}

document — {folder}/document.md (gate after the stage: story-pass, outcome, documented, glossary, architecture)
- `## Glossary`: `| Term | Context | Added or changed | Definition source |` — the last cell names where the definition
  came from; a row without it is an unsourced claim
- `## Documents updated`: `| File | What changed | Verified by |` — the first cell is a path from the project root that
  exists; `Verified by` names the file read or the command run. Nothing updated: one row `| — | none | <what you read> |`
  (`{'`, `'.join(sorted(n for n in NOTHING if n))}` read as no file). `document.md` itself is never listed
- `## Not documented`: `- <thing>: <why, and what it waits for>` — one line each
- every backticked path anywhere in the file resolves from the project root: `src/main/java/com/example/Thing.java:12`,
  `{folder}/build.md:20`; a bare `Thing.java:12` or a package-relative `example/Thing.java` is refused (`documented`)
- `## Paths`, when the pipeline wrote the file's skeleton (`factory-cli.py --document-skeleton <story>`): the story's
  changed files and the run's files in exactly that form — cite from there, do not retype
- every term the plan proposed under `## Glossary proposals` is in a glossary now, or named as still open under
  `## Not documented` (`glossary`). The skeleton pre-fills a `## Glossary` row per proposal — write the entry from it
{GLOSSARY_RULE}
- `## needs-human` only to stop (`decision: <story>-<nn>`, record `stage: document`)"""
    if stage == "review":
        return f"""{CONTRACT_HEAD}

review — {folder}/reviews/<perspective>.md (one per perspective: {', '.join(BUILT_IN_PERSPECTIVES)} and the profile's
`reviews:`; the document gate reads them as `reviews`)
- written by the perspective's carrier — the review skill `review.<perspective>:` names, or `review-<perspective>` — in that
  skill's report format: `## Findings` with `### must-fix`, `### should-fix`, `### nits`, each finding with the file and
  line it stands on and a one-line fix; "nothing found" said plainly where that is the case
- the reviewer reads the diff (`{evidence}/story.diff`), the story, plan.md, tests.md, build.md and the product and
  technical description; it opens a file only where the diff's context does not carry the question; it changes nothing
- the judge converges from these files: it confirms each must-fix and should-fix in the code, drops what it cannot point at,
  deduplicates across perspectives, and names the file it read per perspective under `## Perspectives covered`
- a missing file is a note at the document gate (the judge ran that pass itself and says so); a file without a findings
  section is refused"""
    if stage == "glossary":
        return f"""{CONTRACT_HEAD}

glossary — how the document gate matches a proposed term (`glossary`), and the entry the glossary skill writes
{GLOSSARY_RULE}
- an entry: `### <Term>` — the heading carries the term as the plan proposed it, the domain word with the code word in
  parentheses where they differ (`### Titel (TaskTitle)`) — then `**Definition:**` and `**Type:**` (the glossary skill's
  format; `Type` is one of Aggregate Root, Entity, Value Object, Domain Event, Integration Event, Domain Service,
  Specification, Concept); `Identity`, `Synonyms (avoid)`, `Related terms`, `Operations` where they apply"""
    return None


#: How `check_proposals_landed` finds a proposed term, said once for `--contract document` and `--contract glossary`.
GLOSSARY_RULE = ("- a term is found in a glossary by any of its words: the term as written, the word before a parenthesis or "
                 "the word inside it (`Titel (title)` is found by `titel` or by `title`), case aside; the whole glossary "
                 "file counts, a heading is the place to put it. A term not landed is named open under `## Not documented`, "
                 "nowhere else — a pre-filled `## Glossary` row does not account for it")


#: The section each builder hand-over lists its files in, and the row shape the gate's `listed_files` reads.
FILES_SECTIONS = {
    "test": ("## Files", None, "- `{path}`"),
    "build": ("## Changed", "| File | Why |\n|---|---|", "| `{path}` | |"),
    "tidy": ("## Moves", "| File | Move | Why it reads better |\n|---|---|---|", "| `{path}` | | |"),
}


FILES_SKELETONS = {
    "test": "# Tests — {story}\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n\n## Files\n{rows}\n\n## Notes\n",
    "build": "# Build — {story}\n\n## Changed\n| File | Why |\n|---|---|\n{rows}\n\n## Deviations from the plan\n",
    "tidy": "# Tidy — {story}\n\n## Moves\n| File | Move | Why it reads better |\n|---|---|---|\n{rows}\n\n"
            "## Left alone\n",
}


def changed_for_skeleton(cwd: str, runs: str, story_id: str, stage: str) -> typing.Optional[typing.List[str]]:
    """The files the stage has to list, from the same sources `files-listed` reads and no other: the stage's
    changed-files record where the stage has ended; a shared builder's record, or its open window's tree against
    the story's base, minus what the story's other hand-overs list (the gate checks their union).
    `None` when nothing was observed — the list is then the stage's, as the gate's skip says."""
    folder = evidence_dir(runs, story_id)
    record = os.path.join(folder, f"changed-{stage}.txt")
    if os.path.isfile(record) and not snapshot_reason(record):
        return [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
    # the gate checks the union of the three hand-overs against the builder's record: a file another
    # hand-over lists is not this stage's to list (inside the open window only the earlier ones exist)
    listed = set()
    for name in FILES_SECTIONS:
        if name != stage:
            listed |= listed_files(os.path.join(runs, story_id, STAGE_FILES[name])) or set()
    not_listed = lambda path: path not in listed and not any(path.endswith("/" + n) for n in listed)
    builder = os.path.join(folder, "changed-builder.txt")
    if os.path.isfile(builder) and not snapshot_reason(builder):
        return [path for path in (line.split("\t", 1)[1] for line in read_text(builder).splitlines() if "\t" in line)
                if not_listed(path)]
    base_file = os.path.join(folder, "base-tree")
    if os.path.isfile(base_file):
        base = read_text(base_file).strip()
        now = git_tree(cwd) if base and base != "none" else None
        rows = tree_changes(cwd, base, now, runs) if now else None
        if rows is not None:
            return [path for _kind, path in rows if not_listed(path)]
    return None


def _files_skeleton(runs: str, story_id: str, stage: str, cwd: str = ".") -> int:
    """The stage's hand-over with its file list written by the pipeline: created with the stage's headings
    when the file is missing, or the missing paths added to its list when the stage wrote the file first.
    The stage fills in the why; it never types the list — the one refusal that cost the test stage a
    gate run in the bench. Idempotent: a path already listed is not added twice."""
    if stage not in FILES_SECTIONS:
        print(f"factory: --files-skeleton takes {', '.join(FILES_SECTIONS)}, not {stage!r}", file=sys.stderr)
        return 2
    changed = changed_for_skeleton(cwd, runs, story_id, stage)
    if changed is None:
        print(f"factory: nothing observed — no changed-files record and no base tree for {story_id}; the {stage} "
              f"stage lists its files itself", file=sys.stderr)
        return 1
    heading, header, row = FILES_SECTIONS[stage]
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, STAGE_FILES[stage])
    os.makedirs(folder, exist_ok=True)
    if not os.path.isfile(target):
        rows = "\n".join(row.format(path=path) for path in changed)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(FILES_SKELETONS[stage].format(story=story_id, rows=rows))
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — the skeleton with {len(changed)} path(s) under `{heading}`")
        return 0
    already = listed_files(target) or set()
    missing = [path for path in changed if path not in already and not any(path.endswith("/" + n) for n in already)]
    if not missing:
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} lists every changed file already — nothing added")
        return 0
    lines = read_text(target).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == heading.lower()), None)
    addition = [row.format(path=path) for path in missing]
    if start is None:
        lines += ["", heading] + ([header] if header else []) + addition
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        body = lines[start + 1:end]
        while body and not body[-1].strip():
            body.pop()
        if header and not any(line.lstrip().startswith("|") for line in body):
            body += header.split("\n")
        lines = lines[:start + 1] + body + addition + [""] + lines[end:]
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")
    print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — {len(missing)} path(s) added under `{heading}`")
    return 0


def files_skeleton(runs: str, story_id: str, stage: str, cwd: str = ".") -> int:
    """The stage's file list (below), and at the test stage the `gate:invariants` table with one row per rule the
    plan names — element, number, the rule's text — so the stage fills in only each row's test."""
    code = _files_skeleton(runs, story_id, stage, cwd)
    if code == 0 and stage == "test":
        invariants_skeleton(runs, story_id)
        clauses_skeleton(runs, story_id, cwd)
    return code


def clauses_skeleton(runs: str, story_id: str, cwd: str = ".") -> None:
    """Contract 15: tests.md's `## Clauses` table from the story's scenarios — one row per `Then` and each `And` after
    it, the clause's text written by the pipeline; the stage fills in only `<File>:<line>` and the level. Rows already
    there are kept, missing ones added."""
    if contract_of(read_profile(resolve_profile(None, cwd))) < 15:
        return
    target = os.path.join(runs, story_id, "tests.md")
    try:
        story_path = find_story(place("epics"), story_id)
        wanted = scenario_clauses(read_front_matter(story_path)[1])
    except GateError:
        return
    if not wanted or not os.path.isfile(target):
        return
    text = read_text(target)
    present = {(key, n) for key, n, _loc, _lvl in (read_clause_rows(text) or [])}
    rows = [f"| {key} | {n} | {clause.replace('|', '/')} | | |" for key, clauses in wanted.items()
            for n, clause in clauses if (key, n) not in present]
    if not rows:
        return
    if CLAUSES_MARKER not in text:
        text = text.rstrip("\n") + "\n\n## Clauses\n" + CLAUSES_MARKER + \
            "\n| criterion | n | clause | assertion | level |\n| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
    else:
        lines = text.splitlines()
        at = next(i for i, line in enumerate(lines) if CLAUSES_MARKER in line)
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + rows + lines[end:]
        text = "\n".join(lines).rstrip("\n") + "\n"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"factory: {runs}/{story_id}/tests.md — {len(rows)} clause row(s) under `## Clauses`; fill in each "
          "`<File>:<line>` and level (unit, port, adapter, e2e)")


def invariants_skeleton(runs: str, story_id: str) -> None:
    """tests.md's `## Invariants` table from plan.md's `## Invariants`: one row per rule, the test cell empty for the
    stage to fill; rows already there are kept, missing ones added. Nothing when the plan names no rule."""
    plan_path, target = os.path.join(runs, story_id, "plan.md"), os.path.join(runs, story_id, "tests.md")
    if not os.path.isfile(plan_path) or not os.path.isfile(target):
        return
    named = plan_invariants(read_text(plan_path)) or {}
    wanted = [(element, n, rule) for element, rules in named.items() for n, rule in enumerate(rules, 1)]
    if not wanted:
        return
    text = read_text(target)
    present = {(e, n) for e, numbers, _sel in (read_invariant_rows(text) or []) for n in numbers}
    rows = [f"| {e} | {n} | {rule.replace('|', '/')} | |" for e, n, rule in wanted if (e, n) not in present]
    if not rows:
        return
    if INVARIANTS_MARKER not in text:
        text = text.rstrip("\n") + "\n\n## Invariants\n" + INVARIANTS_MARKER + \
            "\n| element | rule | invariant | test |\n| --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
    else:
        lines = text.splitlines()
        at = next(i for i, line in enumerate(lines) if INVARIANTS_MARKER in line)
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + rows + lines[end:]
        text = "\n".join(lines).rstrip("\n") + "\n"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"factory: {runs}/{story_id}/tests.md — {len(rows)} invariant row(s) under `## Invariants`; fill in each test")


PLAN_SKELETON = ("# Plan — {story}\n\n## Context\n\n## Changes\n| Element | Kind | Location | New or changed | Evidence |\n"
                 "| --- | --- | --- | --- | --- |\n\n## Acceptance criteria\n{rows}\n\n## Spec delta\n{delta}\n\n## Invariants\n\n## Files\n\n## Glossary proposals\n\n"
                 "## Open assumptions\n")


#: A task's plan (WP-106): what changes in the code and where — no criteria, no levels, no spec delta.
TASK_PLAN_SKELETON = ("# Plan — {story}\n\n## Context\n\n## Changes\n| Element | Kind | Location | New or changed | Evidence |\n"
                      "| --- | --- | --- | --- | --- |\n\n## Invariants\n\n## Files\n\n## Open assumptions\n")


def plan_skeleton(runs: str, story_id: str, cwd: str = ".") -> int:
    """`plan.md` before the plan stage runs: the file's headings and, under `## Acceptance criteria`, one line per
    criterion of the story with its key — the stage gives each its level and never retypes the story's text.
    Idempotent: an existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "plan.md")
    if os.path.isfile(target):
        print(f"factory: {runs}/{story_id}/plan.md exists — left as it is")
        return 0
    try:
        story_path = find_story(place("epics"), story_id)
        criteria = criteria_of(story_path, read_front_matter(story_path)[1], read_front_matter(story_path)[0])
    except GateError as error:
        print(f"factory: {error}", file=sys.stderr)
        return 1
    if story_kind(read_front_matter(story_path)[0]) == "task":
        os.makedirs(folder, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(TASK_PLAN_SKELETON.format(story=story_id))
        print(f"factory: {runs}/{story_id}/plan.md — a task's skeleton: no criteria, no spec delta")
        return 0
    rows = "\n".join(f"- {key}  →  level: " for key, _text in criteria)
    # The spec delta as far as it follows from the story and the spec: added, held, changed by key. A removal and
    # a renamed rule are the plan stage's to add — and a change it finds that the story does not say, its question.
    front, body = read_front_matter(story_path)
    target_spec, held, features, feature = story_spec(front)
    story = story_entries(body)
    found = derived(story, held) if target_spec else {}
    delta = "\n".join(f"- {verb} {key}" for key, verb in found.items())
    # Where the story's criteria go (WP-105): a feature the context does not have yet is born, a criterion that stands
    # under another feature moves — both follow from the story and the spec, so the skeleton writes them.
    if target_spec and not journeys_hold(front):
        delta = "\n".join([line for line in (delta,) if line] + placement_lines(story, held, feature, features))
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(PLAN_SKELETON.format(story=story_id, rows=rows, delta=delta))
    print(f"factory: {runs}/{story_id}/plan.md — the skeleton with {len(criteria)} criterion key(s) under `## Acceptance criteria`")
    return 0


def document_skeleton(runs: str, story_id: str, cwd: str = ".") -> int:
    """`document.md` before the document stage runs: the file's headings, and under `## Paths` every file the
    story changed and every run file, as they resolve from the project root. A path the model never types
    cannot be package-relative — the one refusal that cost the document stage its rounds. Idempotent: an
    existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "document.md")
    if os.path.isfile(target):
        return 0
    paths = []
    record = os.path.join(evidence_dir(runs, story_id), "changed.txt")
    if os.path.isfile(record):
        for line in read_text(record).splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0] in ("added", "modified") and os.path.isfile(os.path.join(cwd, parts[1])):
                paths.append(parts[1])
    for name in STAGE_ORDER:
        run_file = os.path.join(folder, STAGE_FILES[name])
        if os.path.isfile(run_file):
            paths.append(f"{runs}/{story_id}/{STAGE_FILES[name]}")
    # the plan's proposals as the glossary table's rows: the term as the plan wrote it — the word the gate
    # looks for — the story's context, and the plan line as the definition's source; the stage writes the
    # glossary entry from the row and never retypes the term (the refusal that cost the bench a second run)
    glossary_rows = ""
    plan_file = os.path.join(folder, "plan.md")
    if os.path.isfile(plan_file):
        context = ""
        try:
            story_path = find_story(place("epics"), story_id)
            context = str(read_front_matter(story_path)[0].get("context", "")).strip()
        except GateError:
            pass
        for term in plan_proposals(read_text(plan_file)):
            glossary_rows += f"| {term} | {context} | added | `{runs}/{story_id}/plan.md` `## Glossary proposals` |\n"
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(f"# Document — {story_id}\n\n## Glossary\n| Term | Context | Added or changed | Definition source |\n"
                     f"|---|---|---|---|\n{glossary_rows}\n## Documents updated\n| File | What changed | Verified by |\n|---|---|---|\n\n"
                     "## Not documented\n\n## Paths\n"
                     "The files this story changed and the run's files, as they resolve from the project root — cite them in "
                     "exactly this form (with `:<line>` where a line matters); the pipeline wrote this list, leave it in place.\n")
        for path in paths:
            handle.write(f"- `{path}`\n")
    terms = glossary_rows.count("\n")
    print(f"factory: {runs}/{story_id}/document.md — the skeleton with {len(paths)} path(s) under `## Paths`"
          + (f" and {terms} proposed term(s) under `## Glossary`" if terms else ""))
    return 0
