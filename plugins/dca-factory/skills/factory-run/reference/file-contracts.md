# File contracts between the stages

Every stage is a closed assignment: it reads the story and its predecessor's file, and it
writes exactly one file of its own. No stage relies on chat history, so a stage can run in a
fresh context, in a subagent or in a separate process without changing the result.

| Stage | Reads | Writes |
|---|---|---|
The run folder is `.dca-factory/runs/` unless the stack profile's `runs:` names another place; the
stories are under `project/epics/` unless `epics:` does.

| `stage-plan` | the story, the project description (`product.md`, `tech.md`, `domain.md`), the stack profile, the project's glossary and generated context map if present, and its existing tests (for `## Changed tests`) | `.dca-factory/runs/<story>/plan.md` — one line per criterion with its level: `- <key>: … → level: e2e \| integration (port) \| integration (adapter: <Adapter>) \| browser-only (<why>)`, and `## Invariants`, one line per domain type it changes; the test gate reads `browser-only` and the invariants |
| `stage-test` | the story, `plan.md`, the product description's qualities where the plan names them | `.dca-factory/runs/<story>/tests.md` (with the `gate:tests` table, the `gate:invariants` table: one row per rule of the plan's `## Invariants`, each with its own unit test, and — contract 15 — the `gate:clauses` table: one row per `Then` and each `And` after it, with the line that asserts it and its level; a clause about what is stored never at `adapter`) |
| `stage-build` | the story, `plan.md`, `tests.md`, the product description's look and qualities | `.dca-factory/runs/<story>/build.md` |
| `stage-tidy` | the story, `plan.md`, `build.md`, and the code as the build stage left it | `.dca-factory/runs/<story>/tidy.md` |
| `stage-judge` | the story and its epic, `plan.md`, `tests.md`, `build.md`, the story diff, the product and the technical description, the profile's `reviews:`/`review.<perspective>:` lines, and in a repeat round `.judge-previous.md` | `.dca-factory/runs/<story>/judge.md` |
| `stage-document` | the story, `plan.md`, `build.md`, `judge.md`, the story diff, the project's documents and glossaries, and its own file as the pipeline's skeleton | `.dca-factory/runs/<story>/document.md` — started by `factory-cli.py --document-skeleton <story>`: the headings, and under `## Paths` every changed path and run file as it resolves from the project root; the stage fills the tables and cites from that section |

The tidy stage's moves reach the judge and the document stage through the story diff, not through
`tidy.md`: what a stage reads is what it needs, not everything that exists.

What the gate holds each file to is printed, in a page, by `factory-cli.py --contract <stage>` — from the
gate's own constants (the table pattern, the selector pattern, the section names), so the text and the
check cannot drift apart. A stage reads that, never the gate's source.

Two processes may carry several stages under one window name in the journal and the changed-files
record: the shared builder (`builder`: plan, test, build, tidy) and the shared verifier (`verifier`: judge,
document). Every stage still writes its own file; the gate reads a window as the stages it carries.

## What changed — `.dca-factory/runs/<story>/.verify/changed-<stage>.txt`, `changed.txt`, `story.diff`

The pipeline records what a story changes; no stage reconstructs it. Around every stage the
runner — or `--stage-start`/`--stage-end` in a session — snapshots the working tree (every file git
reports as differing from HEAD, untracked ones included, with its sha256; a tracked file that is gone
as `deleted`). After the stage the gate writes `changed-<stage>.txt` (`added` / `modified` /
`removed` and a path, one per line), and the story's cumulative `changed.txt` and `story.diff`
against a tree object recorded at the story's first stage — written once, without committing, so a
repository without a commit gets a diff as well and a stage run again does not move the story's
starting point. Paths are the project's, also where the project is a directory inside a larger
repository. The run folder, the installed pipeline (`.agents/factory/`), a story's `decisions/` records and gitignored files are left out. Without
git the tree cannot be compared: the snapshots and the records then carry one line, `# not observed:`
and the reason, `story.diff` says there is no diff, and the gate skips the files check and names the
reason — never "0 files changed".

Each hand-over names files: the plan's `## Files` (what changes, and what a later stage should
read), the tests' `## Files` (the test files written), the build's `## Changed` and the tidy's
`## Moves` tables. The build and tidy gates check those tables against `changed-<stage>.txt`: a
changed file the table does not list fails the gate, a listed file that did not change is a note.
In a table only the first cell names a file; the other cells say why, and a backticked route or `/`
there is prose. A stage that changed no file (a tidy with nothing to tidy) needs no such section.
The next stages open these files first and search the tree only for what they do not answer.

`.dca-factory/runs/<story>/.tests-red` records which selectors the test stage actually saw fail. The build gate
requires each green test to appear in it, because a runner that matched **no** test exits 0 exactly
like a passing one: without the record, a criterion with a mistyped or misplaced test would be
certified green. When the file is absent altogether — the run artefacts need not be committed — the
green run is skipped and named rather than trusted or refused.

Each line is `<selector><TAB><sha256 of the test file>`: a red proof is a proof about one version of
a test. The build and tidy gates compare the digest with the file as it is
(`red-proof`); a test changed after it was seen failing no longer carries its proof, unless an
answered decision of stage `test` changed what it expects. A line without a digest proves the red run
but not the version, so the comparison is skipped and named.

A test changed after its build met it — a round the judge sent back with `back: test` because the
test asserted too little — is green and cannot be seen red again. The test gate asks for its break
instead: `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`, applied to a scratch copy of the
project, must turn it red (`break-proof`, the same proof an adoption gives for a test it wrote); the red
record then holds the test's new version, so the build gate's `red-proof` accepts it.

`.dca-factory/runs/<story>/.rounds` counts the build/judge repeat rounds. It is a file rather than something
the orchestrator remembers, because an in-session run has no other honest way to count and a
resumed run must see the same number. At three the run stops. A refusal on `gate:fail environment` (a
profile command's program missing on the gate's PATH) counts no round. A person's `factory.sh run
--story <id> --from <stage>` starts a new count: the runner moves the file to
`.dca-factory/runs/<story>/.verify/rounds.<UTC time>` and writes a `rounds-reset` line into the journal.

A mapped test is run with the profile command that **covers the file it was found in** — the
end-user tests and the unit tests usually live in different projects or source sets, and a selector
run against the wrong one matches nothing. When no declared command covers that path, the gate says
so instead of guessing.

## One owner per place — the story carries its state, the run folder is protocol

`.dca-factory/runs/<story>/` holds what a run produces: the hand-overs, the marks (`.story-digest`,
`.tests-red`, `.tests-baseline`, `.rounds`, a gate's refusal), the journal and the snapshots under
`.verify/`. Nothing the factory needs *after* a run lives there. Whether a story is delivered stands
in the story itself: the document gate — or the adopt gate — writes `status: delivered` and
`delivered: <UTC time>` into its front matter when it passes (an adopted story keeps `status: adopted`
and gains the date). No stage, no skill and no person writes those two lines; `draft → approved` is
the person's, `→ delivered` the gate's. The plan gate's story digest leaves the two lines out, so a
delivery never reads as "the story changed after it was planned". A reopen (`--reopen`, on an answered
correction the story cites) takes them out again and moves the delivered pass's hand-overs to
`.verify/pass-<n>/`, so the first pass stays readable beside the next.

`.verify/suites.tsv` is the runner's record of the suite runs its own gates made: one row per passing
invocation — the tree it ran on (a digest of the sources, the run folder and the tools' folders left
out), the invocation, its exit code, what the reports said ran, and a signature under a key the runner
hands to its gate processes alone. A later runner gate on the same tree reads its own rows instead of
starting the command again and says so in the report (`recorded at <time> for this tree`). A stage's
own gate run has no key: it writes no row the runner reads, and a row from any other hand carries no
valid signature. A tree that differs by one byte runs everything.

So the run folder is disposable: delete `.dca-factory/` at any time and the schedule, the
dependencies and the status read the same — what is lost is history (hand-overs, journal, tokens),
never what is delivered or decided. Whether the project commits it is its choice (the README says
what that buys). Absent files are skipped and named: a red ledger that is gone makes the green
check a skip, not a pass. One edge the schedule watches: code changed in the checkout that no story's
run folder claims — a folder removed while a story was past its plan, a person's work in progress — is
named and nothing starts on top of it, unless a story was delivered since the last commit (its code
waits for its commit, the normal state).

A story's **id is unique in the whole project**: the run folder and the decision records are named
after it, and the schedule keys stories by it. A second story under the same id is refused by the
backlog check, the plan gate and the schedule, naming both files.

## The `gate:tests` table

`.dca-factory/runs/<story>/tests.md` carries one machine-readable table. The gate reads nothing else from
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
- Every hand-over says what the next stage needs and nothing a reader has elsewhere: the plan lists the
  criteria by key and level, not by the story's text (`factory-cli.py --plan-skeleton <story>` writes the
  headings and the keys); a change row cites one node; no hand-over records the gate's outcome — the gate's
  report under `.verify/` is the evidence, and a stage edits no hand-over after the gate ran. `--contract <stage>`
  names each file's measure — a base plus a share per criterion — and the gate notes a larger file
  (`gate:note size`), never refuses it.
- The `## Files` list (the build's `## Changed` and the tidy's `## Moves` table's first column) is written
  by the pipeline: `factory-cli.py --files-skeleton <story> <stage>` creates the hand-over with every
  changed file listed, or adds the missing paths to one the stage wrote first, from the same record the
  gate's `files-listed` reads. The stage fills in the why.
- The gate starts one process per test command, not per row: every selector a command covers goes
  into one filtered run (`filterJoin` where the runner takes one expression), and each row's verdict
  is read from that run's report by name. Where the build or tidy gate runs a command whole for the
  policy (`required:`), that whole run is the rows' evidence as well. A row the shared run's report
  does not show runs alone once before it fails.
- Every criterion needs at least one row, and the gate looks the test up in the sources: a row
  without a test would look exactly like a red test at the runner, so the run would certify
  nothing. A criterion with no test at all is a criterion the build gate can never fail on.
- Never write a criterion key into a test name, a display name or a comment. The test names the
  behaviour; the table holds the link.

## A story's worktree — `.dca-factory/worktrees/<story>/`

The runner gives every story a git worktree of its own, on a branch `story/<id>` made from the main
checkout's branch, which `.dca-factory/runs/<story>/.verify/target` records. Every stage runs there and
changes code there alone. What is state stays in the main checkout, and the worktree sees it through links
(on Windows junctions): the epics with the stories and their records, the run folder, the discovery
reports, the installed pipeline and the tools' skill folders; the product, technical and domain description
and the profile are copies, read alone. `FACTORY_HOME` names the main checkout to every process in the
worktree, so the gate and the cli read each place from there and leave those paths out of the story's
changes. `.dca-factory/worktrees/` is kept out of the main checkout's status in `.git/info/exclude`.

**The integrate step.** When every gate passed — the document gate, or the adopt gate — the story is not
delivered yet: the gate says `integrate` and the runner integrates it, one story at a time under
`.dca-factory/integrate.lock`. It commits the story's code on its branch, merges the target in and squashes
the whole to one commit, `feat(<context>): <title>` (`test(…)` for an adoption or a journey) with `Story:
<id>` in its body; factory commits carry `--no-verify`, because the integrate gate holds the tree to more than
the hook does. Where the merge stops, the conflicted files are listed in `.verify/conflicts` and the
`stage-integrate` agent resolves them in the worktree, writing `.dca-factory/runs/<story>/integrate.md` (`| File |
The story changed | The main line changed | How both hold |`); the runner commits the resolution. The
integrate gate (`--stage integrate`) then checks the tree as it now is — no unmerged path, no conflict marker
in a file the story's commit changes, the commit on the target's tip (`moved` otherwise, and the step merges
again), the story's tests green, the required suites, `architecture` and `format` — and fast-forwards the main
checkout's branch to the commit. Only then does it write `status: delivered`; a main checkout on another branch,
or with a change of its own in a file the commit touches, is refused (`checkout`) and the story stops until
`factory.sh run --story <id> --from integrate`. A refusal of the checks goes back to the build stage as a round, and
the document stage writes its file anew (the earlier one stays as `.verify/document.before-integrate.md`).
Delivered, the worktree and the branch go.

## Review files — `.dca-factory/runs/<story>/reviews/<perspective>.md`

One file per perspective the judge covers: `ddd`, `hexagonal`, `clean-code` and whatever the profile's
`reviews:` adds, each written by the review skill `review.<perspective>:` names (`review-<perspective>`
where the profile names none), in that skill's report format — `## Findings` with `### must-fix`,
`### should-fix` and `### nits`, every finding with the file and line it stands on and a one-line fix,
"nothing found" said plainly. The runner starts the reviewers at once, before the judge, one process
each; a session starts one subagent each where the tool has them. The judge reads the files and
converges — confirms each finding in the code or drops it with the reason — and names the file per
perspective under `## Perspectives covered`. The document gate reads them as `reviews`: a missing file
is a note (the judge ran that pass itself and says so), a file without a findings section is refused.
A repeat round writes new files; the old ones are not kept. `--contract review` prints the shape.

## Findings — `<story>/findings.md`, in the story's folder

The judge's confirmed defects that did not block the story — its minors — written by the document gate when it
delivers the story, from `judge.md`'s `## Confirmed defects` table: one row per finding, `| # | Perspective |
File:line | Severity | Defect | Fix | Status |`, `Status` `open`; a row already there (same file:line and defect)
is not written twice. The file lives in the story's folder beside its `decisions/`, is committed with the project
and is no story to the backlog. A person sets `done` or `wont-fix`; a later story may take the open rows as its
brief. `factory-cli.py --findings` lists the open rows, and the status brief counts them.

## Escalation

A stage that cannot finish writes its file anyway, with a `## needs-human` section, and the
orchestrator stops the run at that point. Two situations always escalate rather than being solved:

- the plan would need a new bounded context or a new relationship between contexts;
- three build/judge rounds in a row did not converge.

The section names the question as a **decision record** (below): `decision: <id>` on its own
line. A `## needs-human` without one has asked nobody, and the next gate refuses it.

## Decision records — `<story>/decisions/<nn>.md`, in the story's folder

The question a stage may not answer, kept as a file of its own so the answer has a place to land
and a second session — or the same one tomorrow, or another tool — finds it without any
transcript. It lives in the folder of the story it belongs to, `project/epics/<epic>/<story>/decisions/<nn>.md`
(an acceptance as `accept-<n>.md`), because a human's answer is human-written state and belongs in
the people's place; committed with the story. The record's `id:` is `<story>-<nn>` (`<story>-accept-<n>`),
which is how stages, the gate and the inbox cite it, and the file is found by that name: a record
whose `id:` or `story:` does not match its place is refused. Markdown with front matter, from
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
  the one that asked: an answer that changes a test is `applies: test`, whichever stage asked, so the changed
  test gets its red proof at the test stage. The story resumes at the **earlier** of `stage:` and `applies:` —
  a plan's question answered `applies: test` re-plans first and lists the tests that change — and the test
  stage's "expectation changed on a decision" reads `applies:` before `stage:`.
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
  not a refusal; the runner stops and counts no round. `factory-cli.py --reopen <story>` takes a
  delivered story back for a correction the story cites — not while another story holds the checkout
  with unfinished code; after an accepted record it refuses a correction that changes a criterion
  (a new wish is a new story).
- Only a human writes `## Answer`, or a skill writing the human's exact words on their explicit
  confirmation. A recommendation, a timeout, a preselected option or an unconfirmed draft is not
  an answer.
- The stage the story resumes at (the earlier of `stage:` and `applies:`) **applies** the answer when it runs again: its new file no longer ends in
  `## needs-human` and cites the id where the answer landed (`Decision US-3-01 answered b: …`).
  The gate then stamps `## Applied` into the record. Applied means the plan carries the answer,
  not that the story is delivered.
- The gate checks the store on **every** stage: an open record blocks the story wherever it
  stands, and the runner does not start a stage while one is open.
- `python3 .agents/factory/factory-cli.py --list-decisions [--story <id>]` prints the inbox — one
  line per record, open first — which is what the `factory-decisions` skill shows and works from.

What this does not do, on purpose: no leases, no revision numbers, no stale-answer detection when
the story changes underneath, no authorisation beyond `by:`. Files writable by the same user give
process guarantees, not security ones.

## Tests that existed before the story — `.dca-factory/runs/<story>/.tests-baseline`

The plan gate runs before any stage of a story touches a test. In a git repository it records every
test file — found by name: `test_*.py`, `*Test.java`, `*Tests.cs`, `*IT.java`, `*.spec.ts`,
`*_spec.rb` and the like — as a git blob, once per story. The test, build and tidy gates compare
against it: a file that still holds every line it had, in order and outside a comment, has only
gained cases and passes. A file whose lines changed only around its assertions passes with a note: every
assertion statement it had — an `assert…`, `expect…`, `verify…` or `should…` call with its chain — is still
there, its words and literals in the same order, at most with more arguments (a type the test builds
gained a field). A changed expected value, a weaker matcher or a removed assertion is no such change. Any
other changed or removed line — or an added line that switches a test off, such
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
