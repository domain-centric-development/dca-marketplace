# File contracts between the stages

Every stage is a closed assignment: it reads the story and its predecessor's file, and it
writes exactly one file of its own. No stage relies on chat history, so a stage can run in a
fresh context, in a subagent or in a separate process without changing the result.

| Stage | Reads | Writes |
|---|---|---|
| `stage-plan` | the story, the project description (`product.md`, `tech.md`, `domain.md`), the stack profile, the project's glossary and generated context map if present, and its existing tests (for `## Changed tests`) | `tasks/<story>/plan.md` — one line per criterion with its level: `- <key>: … → level: e2e \| integration \| browser-only (<why>)`; the test gate reads `browser-only` |
| `stage-test` | the story, `plan.md`, the product description's qualities where the plan names them | `tasks/<story>/tests.md` (with the `gate:tests` table) |
| `stage-build` | the story, `plan.md`, `tests.md`, the product description's look and qualities | `tasks/<story>/build.md` |
| `stage-tidy` | the story, `plan.md`, `build.md`, and the code as the build stage left it | `tasks/<story>/tidy.md` |
| `stage-judge` | the story, `plan.md`, `tests.md`, `build.md`, the story diff, the product and the technical description, the profile's `reviews:`/`review.<perspective>:` lines, and in a repeat round `.judge-previous.md` | `tasks/<story>/judge.md` |
| `stage-document` | the story, `plan.md`, `build.md`, `judge.md`, the story diff, the project's documents and glossaries | `tasks/<story>/document.md` |

The tidy stage's moves reach the judge and the document stage through the story diff, not through
`tidy.md`: what a stage reads is what it needs, not everything that exists.

## What changed — `tasks/<story>/.verify/changed-<stage>.txt`, `changed.txt`, `story.diff`

The pipeline records what a story changes; no stage reconstructs it. Around every stage the
runner — or `--stage-start`/`--stage-end` in a session — snapshots the working tree (every file git
reports as differing from HEAD, untracked ones included, with its sha256; a tracked file that is gone
as `deleted`). After the stage the gate writes `changed-<stage>.txt` (`added` / `modified` /
`removed` and a path, one per line), and the story's cumulative `changed.txt` and `story.diff`
against a tree object recorded at the story's first stage — written once, without committing, so a
repository without a commit gets a diff as well and a stage run again does not move the story's
starting point. Paths are the project's, also where the project is a directory inside a larger
repository. Run artefacts (`tasks/`, `.agents/factory/`) and gitignored files are left out. Without
git there is no diff, and `story.diff` says so.

Each hand-over names files: the plan's `## Files` (what changes, and what a later stage should
read), the tests' `## Files` (the test files written), the build's `## Changed` and the tidy's
`## Moves` tables. The build and tidy gates check those tables against `changed-<stage>.txt`: a
changed file the table does not list fails the gate, a listed file that did not change is a note.
The next stages open these files first and search the tree only for what they do not answer.

`tasks/<story>/.tests-red` records which selectors the test stage actually saw fail. The build gate
requires each green test to appear in it, because a runner that matched **no** test exits 0 exactly
like a passing one: without the record, a criterion with a mistyped or misplaced test would be
certified green. When the file is absent altogether — the run artefacts need not be committed — the
green run is skipped and named rather than trusted or refused.

Each line is `<selector><TAB><sha256 of the test file>`: a red proof is a proof about one version of
a test. The build and tidy gates compare the digest with the file as it is
(`red-proof`); a test changed after it was seen failing no longer carries its proof, unless an
answered decision of stage `test` changed what it expects. A line without a digest proves the red run
but not the version, so the comparison is skipped and named.

`tasks/<story>/.rounds` counts the build/judge repeat rounds. It is a file rather than something
the orchestrator remembers, because an in-session run has no other honest way to count and a
resumed run must see the same number. At three the run stops.

A mapped test is run with the profile command that **covers the file it was found in** — the
end-user tests and the unit tests usually live in different projects or source sets, and a selector
run against the wrong one matches nothing. When no declared command covers that path, the gate says
so instead of guessing.

`tasks/` holds run artefacts. Whether they are committed is the project's choice; the pipeline
only requires that a stage finds its predecessor's file.

## The `gate:tests` table

`tasks/<story>/tests.md` carries one machine-readable table. The gate reads nothing else from
the file:

```markdown
<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-empty-state | com.example.reporting.MonthlyReportPageTest#showsEmptyState |
| lists-entries | com.example.reporting.MonthlyReportPageTest#listsEntries |
```

- `criterion` is the key from the story's acceptance criteria.
- `test` is `<fully qualified class>#<method>`. The class part is a dotted name: a class in a
  file named after it (`com.example.WidgetTest`), or a module path with an optional class in it
  (`tests.test_widgets`, `tests.test_widgets.TestWidgets`). The stack profile decides how that
  becomes a filter argument for the runner (`filterFormat`, with `{class}`, `{method}` and the
  located `{file}`).
- Every criterion needs at least one row, and the gate looks the test up in the sources: a row
  without a test would look exactly like a red test at the runner, so the run would certify
  nothing. A criterion with no test at all is a criterion the build gate can never fail on.
- Never write a criterion key into a test name, a display name or a comment. The test names the
  behaviour; the table holds the link.

## Escalation

A stage that cannot finish writes its file anyway, with a `## needs-human` section, and the
orchestrator stops the run at that point. Two situations always escalate rather than being solved:

- the plan would need a new bounded context or a new relationship between contexts;
- three build/judge rounds in a row did not converge.

The section names the question as a **decision record** (below): `decision: <id>` on its own
line. A `## needs-human` without one has asked nobody, and the next gate refuses it.

## Decision records — `.agents/factory/decisions/<story>-<nn>.md`

The question a stage may not answer, kept as a file of its own so the answer has a place to land
and a second session — or the same one tomorrow, or another tool — finds it without any
transcript. Committed with the project. Markdown with front matter, from
`templates/decision.md.tmpl`:

```markdown
---
id: US-3-01
story: US-3
stage: plan
asked: 2026-09-22T20:40:00Z
---

# Does an archived entry count?

## Question
<what is asked, why this stage may not decide it, the evidence read>

## Options
- a: <one way>
- b: <another>

## Recommendation
<the stage's view — never an answer>

## Answer
answer: b
by: the-expert
at: 2026-09-22T21:00:00Z
rationale: <optional>
```

- `id` is `<story>-<nn>`, `nn` the next two-digit number among the story's records, and it is
  the file name — the gate finds a record by its name and refuses one whose `id:` disagrees.
- `stage` is the stage that re-runs once the answer is there and applies it — the stage that asked,
  except for a judge's story conflict, where it is the stage the answer lands in (`plan` or `test`).
  A test whose expectation changes on such a decision may be green at the test gate when it was
  recorded red before; without the decision, green before the build is refused.
- `applies: <stage>` in the `## Answer` — optional — names the stage that applies this answer when it is not
  the one that asked: an answer that changes a test is `applies: test`, whichever stage asked, so the story
  resumes at the test stage and the changed test gets its red proof there. The gate, the schedule and the
  test stage's "expectation changed on a decision" read `applies:` before `stage:`.
- The state is **read off the file, never stored in it**: no `## Answer` is *open*; an
  `## Answer` with `answer:`, `by:` and `at:` is *answered*; a gate-written `## Applied` is
  *applied*. An `## Answer` missing the name or the time is a draft, and a draft unblocks nothing.
- **An acceptance record** — `id` `<story>-accept-<n>`, front matter `kind: acceptance`,
  `stage: document` and `digest:` (the story's SHA-256 when it was asked) — is written by the
  document gate where the profile's `acceptance:` applies, in place of delivering. It lists the
  criteria with their tests and the profile's `run:` command. `answer: accepted` given for the story
  as it still is delivers it at the next document gate; any other answer is a correction, written
  into the same story (criteria, an `answered:` line citing the id), which then runs again from
  plan and is asked again in a record of its own. The gate exits 3 while one is open — a question,
  not a refusal; the runner stops and counts no round. `story-gate.py --reopen <story>` takes a
  delivered story back for a correction the story cites — not while another story holds the checkout
  with unfinished code; after an accepted record it refuses a correction that changes a criterion
  (a new wish is a new story).
- Only a human writes `## Answer`, or a skill writing the human's exact words on their explicit
  confirmation. A recommendation, a timeout, a preselected option or an unconfirmed draft is not
  an answer.
- The stage that applies it (`applies:`, else the stage that asked) **applies** the answer when it runs again: its new file no longer ends in
  `## needs-human` and cites the id where the answer landed (`Decision US-3-01 answered b: …`).
  The gate then stamps `## Applied` into the record. Applied means the plan carries the answer,
  not that the story is delivered.
- The gate checks the store on **every** stage: an open record blocks the story wherever it
  stands, and the runner does not start a stage while one is open.
- `python3 .agents/factory/story-gate.py --list-decisions [--story <id>]` prints the inbox — one
  line per record, open first — which is what the `factory-decisions` skill shows and works from.

What this does not do, on purpose: no leases, no revision numbers, no stale-answer detection when
the story changes underneath, no authorisation beyond `by:`. Files writable by the same user give
process guarantees, not security ones.

## Tests that existed before the story — `tasks/<story>/.tests-baseline`

The plan gate runs before any stage of a story touches a test. In a git repository it records every
test file — found by name: `test_*.py`, `*Test.java`, `*Tests.cs`, `*IT.java`, `*.spec.ts`,
`*_spec.rb` and the like — as a git blob, once per story. The test, build and tidy gates compare
against it: a file that still holds every line it had, in order and outside a comment, has only
gained cases and passes; a changed or removed line — or an added line that switches a test off, such
as `@Disabled`, `[Fact(Skip = …)]`, `@pytest.mark.skip`, `it.skip(` or `.only(` — fails `tests-kept`
unless it is **authorised**:

- the plan lists the file under `## Changed tests` and the story says `## Changed expectations`, in
  at least one list item a person wrote (a `{{…}}` placeholder or the template's prose is none) —
  the human released a story that changes that behaviour, and the plan found the tests (A); or
- the plan lists the file and its row cites an answered decision of this story — the plan stage found
  contradicting tests the story did not mention and asked once, with the list (B); or
- the story has an answered decision of stage `test` — a judge's conflict landed there.

A listed file without either backing fails, and so does a changed file the plan does not list. Outside git the check is skipped and named, and so is a file whose recorded blob `git gc` has pruned. What it does not see: a test this story itself
wrote and later rewrote, and a test file named against the conventions.

## The change policy — `required:` in the stack profile

`story-gate.py --change` checks a change outside a story; `--staged` checks the Git index and refuses
when the working tree differs from it. The profile's `required:` line lists the checks that must
hold: `compile`, `architecture`, `format`, and each test command by its own profile key (`test`,
`test.<name>`, `e2eTest`), so an end-user suite that needs a running system can be declared without
every commit waiting for one. A required check fails when its command is not declared (at the build and tidy gates too) or — for
a test command — when no report written by the run shows an executed case. A required check outside
this run's scope (`--checks`) is reported as not run here, for a later scope such as CI to run; this
run does not fail on it. Once `required:` is declared, the policy decides: a check outside it that
ran red or ran nothing is reported, and does not fail the verdict.

Without `required:` nothing is mandatory, and what runs still counts: a declared command that runs
red fails, a command that is not declared is skipped and named. So "skipped and named, never failed"
holds for what the project did not declare, not for what `required:` names. A gate that does not know
the key would pass what the project declared mandatory, which is why the key needs file contract 3.

## Scenario contract — for `--parity`

Markdown, one scenario per `## <id>` heading, with two lines under it:

```markdown
## scenario.thing.shown
Title: The reader sees the thing
Runs: always
```

`Title:` is the binding: a test report names the scenario by carrying the title verbatim as the
test's name (JUnit XML `testcase/@name`, TRX `UnitTestResult/@testName` — a display name in both).
`Runs: always` is mandatory in every implementation; any other value names the configuration the
scenario is bound to, and a run that skips it is reported as *not proven here*, not as passed. The
parity config is flat `key: value`, paths relative to the config file:

```
scenarios: spec/scenarios.md
implementation.first: first/build/test-results/e2e/*.xml
implementation.second: second/tests/E2e/TestResults/*.trx
```

The check reads whatever reports match: delete stale ones, or point the glob at one run's output,
before trusting the verdict.
