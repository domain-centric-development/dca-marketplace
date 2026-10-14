# File contracts between the stages

Every stage is a closed assignment: it reads the story and its predecessor's file, and it
writes exactly one file of its own. No stage relies on chat history, so a stage can run in a
fresh context, in a subagent or in a separate process without changing the result.

| Stage | Reads | Writes |
|---|---|---|
The run folder is `.dca-factory/runs/` unless the stack profile's `runs:` names another place; the
stories are under `product/epics/` unless `epics:` does.

| `stage-plan` | the story, the project description (`overview.md`, `tech.md`, `domain.md`), the story's context's spec (`product/spec/<context>/scenarios.md`), the stack profile, the project's glossary and generated context map if present, and its existing tests (for `## Changed tests`) | `.dca-factory/runs/<story>/plan.md` — one line per criterion with its level: `- <key>: … → level: e2e \| integration (port) \| integration (adapter: <Adapter>) \| browser-only (<why>)`, and `## Invariants`, one line per domain type it changes; the test gate reads `browser-only` and the invariants |
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

## What changed — `.dca-factory/evidence/<story>/changed-<stage>.txt`, `changed.txt`, `story.diff`

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

`.dca-factory/evidence/<story>/.tests-red` records which selectors the test stage actually saw fail. The build gate
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

A merge of the main line into the story's branch can change a test this way too — the resumed story's merge,
the integrate stage's resolution of a test both sides changed, the round after an integrate gate refused. The
runner does not hand such a story to build or tidy, whose gates would refuse `red-proof`: before a run starts at
either, it compares the record's digests with the mapped test files, and where one moved (and no answered decision
of stage `test` covers it) the story starts at its test stage instead — a `red-stale` line in the journal, no
round counted. The test stage records each named test as it now is, red where the code before the story fails
it, else with its break, and changes nothing it asserts; build and tidy then run on that record. An answered
decision of a later stage waits for that stage: the test gate notes it, the later gate checks it was applied.
No stage asks about a stale red proof.

`.dca-factory/evidence/<story>/.rounds` counts the build/judge repeat rounds. It is a file rather than something
the orchestrator remembers, because an in-session run has no other honest way to count and a
resumed run must see the same number. At three the run stops. A refusal on `gate:fail environment` (a
profile command's program missing on the gate's PATH) counts no round. A person's `factory.sh run
--story <id> --from <stage>` starts a new count: the runner moves the file to
`.dca-factory/evidence/<story>/rounds.<UTC time>` and writes a `rounds-reset` line into the journal.

A mapped test is run with the profile command that **covers the file it was found in** — the
end-user tests and the unit tests usually live in different projects or source sets, and a selector
run against the wrong one matches nothing. When no declared command covers that path, the gate says
so instead of guessing.

## The journal — `.dca-factory/evidence/<story>/journal.tsv`

One line per event, tab-separated: `<UTC time>\t<kind>\t<name>\t<field>=<value>…\tseq=<n>`. The sequence
number orders the events, never the clock (after a union merge repeated a number, the time decides between the two): two events in one second are told apart by it, and which hand-over
belongs to the story's current pass is read from it alone — no file time is compared. Every line is appended
through one function of the gate, under the journal's lock (the folder `journal.tsv.lock`); the runner composes
its lines and pipes them through `factory-cli.py --journal-line <story>`. Nothing else writes the file, and
nothing rewrites it. A line without `seq=` takes its position in the file.

| Kind | Name | Fields | Written by |
|---|---|---|---|
| `stage-start` | the stage, `builder`, `verifier`, `review:<perspective>` or `integrate` | `tool=`; `model_requested=` and `model_applied=no (<why>)` where the profile names a model; `stages=` for a shared window | the runner, `--stage-start` |
| `stage-end` | as at its start | `exit=0`, `nonzero` or `owned` | the runner, `--stage-end` |
| `step-start` · `step-end` | the runner's own step: `integrate` (merge, gate, fast-forward), `merge` (a resumed story brought onto the main line), `format` (`formatFix:` over a resolution) | `by=runner` at the start, `exit=0` or `stopped` at the end | the runner — read as running where no stage runs; no stage's figures count it |
| `window-start` · `window-end` | the work outside a stage (`backlog`, `decisions`) | `tool=` at the start | `--window-start`, `--window-end` |
| `usage` | the stage or the window | `tool=`, then `model=`, `input=`, `cache_read=`, `cache_write=`, `output=`, `cost=` where the tool reports a price and `seconds=` for a runner invocation — or `unknown`; in a session `window=<start>/<end>` with `session=<tool>:<id>` until the log is read, then a second line with the numbers and the same `window=` | the runner, the stage and window marks |
| `gate` | the stage the gate ran for | `exit=<n>`; `fail=<check>,…` on a refusal; `by=runner`, `by=<stage>` (a stage's own run under the runner) or `by=session`; the plan gate's refusal adds `backlog=<digest>` of the story and its epic | the gate, on every run over a story |
| `wrote` | a hand-over: `plan.md`, `tests.md`, `build.md`, `tidy.md`, `judge.md`, `document.md` | `sha=<digest>` of its content, `sha=gone` once it is removed; `same=1` for a file of the window's stages that a window run to its end left as it was | the gate, at a window's start and end and at every gate run, for each file whose content differs from its last `wrote` |
| `outdated` | `document.md` | `by=integrate` | the runner, when the integrate gate refuses |
| `rounds-reset` | `-` | `by=--from` | the runner, on `run --from` |
| `pipeline-changed` | the stage before whose gate the installed pipeline differed | — | the runner |
| `owned-confirmed` | the parts a person confirmed, comma-separated | — | `--owned-confirm` |

**The current pass.** A stage file counts from its last `wrote`, or from a later pass of its own gate (or its exit 3: every check passed, a person is asked) for
`test`, `build`, `tidy` and `document` — those gates run after their file is written, so a pass vouches for the
file as it stands. An `outdated` after that makes it an earlier pass's. In the stages' order, a file that counts
from before the file ahead of it belongs to an earlier pass, and so does every file after it. A plan refusal holds
while the story and its epic still match its `backlog=` digest; an integrate refusal holds until a `wrote
build.md` follows it. A skeleton (`plan.md`, `document.md`) is the pipeline's only where the pipeline wrote it in
that run: a file an earlier pass left is the stage's to bring up to date or leave as it is, and its gate decides.

**Refusals.** `factory-cli.py --refusals [--story <id>] [--format json]` (`factory.sh status --refusals`) counts
each story's `gate` lines with `exit=1`: the runner's (`by=runner`, or no `by`) apart from the stages' own
self-checks, and each refusal as *form* when every check it names is one about how a hand-over is written
(`files-listed`, `story-pass`, `tests-mapped`, `test-titles`, `plan-levels`, `levels`, `documented`, `decisions`,
`reviews`, `layout`), as *substance* otherwise.

## One owner per place — the story carries its state, the run folder is protocol

`.dca-factory/runs/<story>/` holds what the stages hand over: the hand-overs, their skeletons, a gate's
refusal. What proves a stage's work lies beside it, in `.dca-factory/evidence/<story>/`: the marks
(`.story-digest`, `.tests-red`, `.tests-baseline`, `.rounds`), the journal, the snapshots, the changed-files
records, the base tree and the tools' output. The gate and the runner write the evidence folder; a stage reads
it and never writes there — the runner names it to no tool as a folder to write. `.owned-digest` holds, while a
stage window is open, the digest of what is the person's — the story file and every decision's `## Answer`; the
window's end compares, and a change leaves `.owned-changed`: the story is stopped and the gate refuses (`owned`)
until `factory-cli.py --owned-confirm <story>`. The gate's own writes (delivered, reopened, `## Applied`) are
not a change. Nothing the factory needs
*after* a run lives in either. Whether a story is delivered stands
in the story itself: the gate that delivers — the document gate, the adopt gate, or in a story's worktree the
integrate gate, all through one function — writes `status: delivered`, `delivered: <UTC time>` and
`delivered_by: gate` into its front matter when it passes; built or adopted, the three lines are the same (one
end state). No stage and no skill writes them; `draft → approved` is the person's, `→ delivered` the gate's — or
a person's who delivered the story by hand (`delivered_by: hand:<who>`, `--deliver-by-hand`), a claim the views
show as such until `--prove` has the adopt path check it. The plan gate's story digest leaves the three lines
out — the front matter read by lines, a `---` inside a line is text — so a delivery never reads as "the story
changed after it was planned". When the gate stamps an answer `## Applied`, it writes the answer into the story
as an `answered:` line under `## Assumptions` and takes the planned digest anew in the same write; any other
change after plan still re-plans. A reopen (`--reopen`, on an answered
correction the story cites) takes the lines out again and moves the delivered pass's hand-overs to
`.dca-factory/evidence/<story>/pass-<n>/`, so the first pass stays readable beside the next.

`.dca-factory/evidence/<story>/suites.tsv` is the runner's record of the suite runs its own gates made: one row per passing
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
  report in `.dca-factory/evidence/<story>/` is the evidence, and a stage edits no hand-over after the gate ran. `--contract <stage>`
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
checkout's branch, which `.dca-factory/evidence/<story>/target` records. Every stage runs there and
changes code there alone. What is state stays in the main checkout, and the worktree sees it through links
(on Windows junctions): the epics with the stories and their records, the run folder, the discovery
reports, the installed pipeline and the tools' skill folders; the product, technical and domain description
and the profile are copies, read alone. `FACTORY_HOME` names the main checkout to every process in the
worktree, so the gate and the cli read each place from there and leave those paths out of the story's
changes. `.dca-factory/worktrees/` is kept out of the main checkout's status in `.git/info/exclude`.

**The integrate step.** When every gate passed — the document gate, or the adopt gate — the story is not
delivered yet: the gate says `integrate` and the runner integrates it, one story at a time under
`.dca-factory/integrate.lock`. It commits the story's code on its branch — every tracked file it changed and the
untracked ones a stage window made (`.dca-factory/evidence/<story>/stages-made.txt`, kept across rounds); an
untracked file no stage made, such as a gate command's report nobody ignored, stays out and is named — merges the
target in and squashes
the whole to one commit, `feat(<context>): <title>` (`test(…)` for an adoption or a journey) with `Story:
<id>` in its body; factory commits carry `--no-verify`, because the integrate gate holds the tree to more than
the hook does. Where the merge stops, the conflicted files are listed in `.dca-factory/evidence/<story>/conflicts` and the
`stage-integrate` agent resolves them in the worktree, writing `.dca-factory/runs/<story>/integrate.md` (`| File |
The story changed | The main line changed | How both hold |`); the runner commits the resolution. With the
conflicts the runner records the main line's side of the tests in `.dca-factory/evidence/<story>/main-tests`
(`<base blob | ->\t<main blob>\t<file>` for every test file the main line changed since the story began); a
resolution that leaves out a line the main line added to one of them — a case another story wrote — goes back to
the integrate stage with the file and the lines named, at most twice, before any other stage runs: it is the
resolution's change, never the story's, so neither `tests-kept` nor a person sees it. The
integrate gate (`--stage integrate`) then checks the tree as it now is — no unmerged path, no conflict marker
in a file the story's commit changes, the main line's side of every test the merge met (`main-tests`, refused by
name and sent back to the integrate stage the same way, no round counted), the commit on the target's tip (`moved` otherwise, and the step merges
again), the story's tests green, the required suites, `architecture` and `format` — and fast-forwards the main
checkout's branch to the commit; where the main line gained a commit while the gate ran, that too is `moved`, and
the step merges again, at most three times. Only then does it write `status: delivered`, and the files that delivery
wrote — the story's folder (state, decisions, findings) and the spec it merged — are committed on the main line by
path, `chore(<context>): deliver <id>`, nothing else of the main checkout with them, so the next story's worktree
starts from them. A main checkout on another branch,
or with a change of its own in a file the commit touches, is refused (`checkout`) and the story stops until
`factory.sh run --story <id> --from integrate`. The whole step is journaled as the runner's own
(`step-start integrate` … `step-end integrate`), so the status shows it running with its clock. A refusal of the checks goes back to the build stage as a round, and
the journal marks `document.md` an earlier pass's (`outdated document.md by=integrate`): the document stage writes it
for the story as it now is, or its gate passes it as it stands.
Delivered, the worktree and the branch go. A story set `superseded` with a worktree, or a worktree whose id no story
has any more, loses both when the runner next starts; nothing of it reaches the main line.

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
delivers the story, from `judge.md`'s `## Confirmed defects` table (`| Perspective | File:line | Severity | In plain
words | Defect | Fix |`): one row per finding, `| # | Perspective | File:line | Severity | In plain words | Defect |
Fix | Status |`, `Status` `open`; a row already there (same file:line and defect) is not written twice. `In plain
words` is the one sentence a person reads first — the status JSON's `plain`, which the inbox leads with; a judge
row without it is a note at delivery. A judge table or a findings file from before contract 23 has no such column:
it is read with the sentence empty, and a findings file gains the empty column when the next row is added to it. The file lives in the story's folder beside its `decisions/`, is committed with the project
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
transcript. It lives in the folder of the story it belongs to, `product/epics/<epic>/<story>/decisions/<nn>.md`
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
<the stage's view, opening with the label it recommends — never an answer>

## Answer
answer: b
by: the-expert
at: 2026-09-22T21:00:00Z
rationale: <optional>
```

- `## Options` holds one list item per option in the one canonical form `- a: <text>` — a lowercase
  letter, a colon, plain text, continuation lines indented. The reader (`decision_options` in the package) also
  takes the forms older records carry (`a.`, `a)`, `**a — …**`), and it is the only one: the inbox's JSON lists
  each record's `options` and `recommended` from it, and an answer naming a label becomes that option's first
  line in the story's `answered:` line.
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

## Tests that existed before the story — `.dca-factory/evidence/<story>/.tests-baseline`

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

When the runner brings the main line into a story's worktree (a resumed story, the integrate step), "existed
before this story" moves with the base tree: every test in the main line's tree is recorded as the main line has it,
and one the main line removed leaves the baseline. The main line's tree never holds the story's change, so a test
the story changed before the merge — committed by the runner's merge or not — is still compared against what it
was; in a worktree the gate never takes a test's version from `HEAD`, whose commits are the story's.

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
