---
name: factory-run
description: Runs one backlog story through the delivery pipeline — plan, test, build, tidy, judge, document — with a deterministic story gate between the stages, and several stories in dependency order. Use when the user asks to deliver, implement or run a story or ticket end to end ("run story X", "deliver US-3", "/factory-run"), to work through the backlog ("run the backlog", "deliver everything that is ready", "/factory-run" without a story), to deliver a wish in prose ("/factory-run show the newest products on the homepage" — it becomes a backlog story first), or to keep a session working on the backlog as it fills; a project without a pipeline goes to /factory-setup first. Reads the backlog, the stack profile and the hand-over files — no project knowledge of its own.
---

# Run one story

You are the orchestrator. You own the order of the stages, the file contracts between them, the
gate calls and the escalation. You do **no** domain work yourself: no plan, no test, no
production code, no review verdict. That belongs to the stage assignments below, and keeping
them apart is what makes a run reproducible.

This file is the route; the detail sits in `reference/`, named at the step that needs it. Read a
reference when its step comes, not before.

## What the run needs

| Thing | Where | Missing? |
|---|---|---|
| the project description | `product/overview.md`, `product/tech.md` (and the optional designed map `product/domain.md`), or where the profile points | `/factory-setup` writes it with the person, through the project's description skill; stop and say so |
| the story | `product/epics/<epic>/<story>/story.md`, or under the profile's `epics:` | offer to write one (`/factory-backlog`) and stop |
| the epic | `product/epics/<epic>/epic.md` | same |
| the stack profile | `dca-factory.profile.yaml` | create it from the template by detecting the build (`reference/first-run.md`) |
| an architecture the gate can check | the project's rule suite and building blocks | this is **not** the pipeline's job: the project installs it once with the method's setup skill (in a DCA project `/dca-init`), and the factory never calls a skill that writes code. Without one, the build gate skips the architecture check and names it |
| the gate | `.agents/factory/story-gate.py` — it decides; `factory-cli.py` beside it shows and coordinates (status, schedule, marks, the checkout) | the installer writes both |
| the commit guard | `.githooks/pre-commit` | the installer writes it and sets `core.hooksPath` |

Read `reference/backlog-contract.md` for the backlog format and `reference/file-contracts.md`
for what each stage reads and writes. Both are part of this skill.

An empty project is not an error. Nothing here fails because an artefact does not exist yet —
say precisely which file to create, create it when the user agrees, then continue.

## First run in a project

The entry is `/factory-setup`: it checks the project description, git, the runner and the stack
profile, and does only what is missing. Asked to run a story in a project without a pipeline, say so
and hand over to it. What it installs, how the profile's commands are detected from the presets
(never assumed — a command the project has not is left out, and the gate names the skipped check),
and how a capability is added later with one profile line: `reference/first-run.md`.

## The run

Call the gate as `python3 .agents/factory/story-gate.py --story <id> --stage <plan|test|build|tidy|document>`
from the project root. Exit code 0 means proceed; any `gate:fail` line stops the stage that was
about to run, and the fix belongs to the stage that produced the artefact, not to you.

1. **gate `plan`** — refuses an incomplete epic, a story without a context or criteria, a story
   still in `draft`, and a context that is not on the designed map (or, without one, the generated
   map). It also reports when the project's instruction file is past the size a tool loads, since the
   rest is truncated in silence. Do not repair the backlog yourself beyond obvious typos; an epic
   without an intent is a question for the story's `domain_contact`.
2. **`stage-plan`** → `.dca-factory/runs/<story>/plan.md`
3. **`stage-test`** → `.dca-factory/runs/<story>/tests.md`
4. **gate `test`** — every criterion mapped, test sources compile, every mapped test red. A
   mapped test that is already green means the criterion is not new behaviour or the test asserts
   nothing; send it back to `stage-test`. It also holds the levels: a test the end-user command runs
   must belong to the happy path or to a scenario the plan gave `browser-only`.
5. **`stage-build`** → `.dca-factory/runs/<story>/build.md`
6. **gate `build`** — every mapped test green, and the profile's `architecture:` and `format:`
   commands succeed. Both run in the gate, not on a stage's word. On failure, hand the gate output
   back to `stage-build`. Every repeat round — this one, a refused gate after any stage, a judge's
   `changes-requested` — increments `.dca-factory/evidence/<story>/.rounds`; at **three** the run
   stops and escalates. The counter is a file, not something you remember — an in-session run has
   no other honest way to count, and a resumed run must see the same number. Two refusals count no
   round: `gate:fail environment` — a profile command whose program the gate's shell did not find,
   which no stage can fix; stop and name it — and none at all when a person restarts the story with
   `--from`, which starts a new count (the runner keeps the old one under `.dca-factory/evidence/<story>/`).
7. **`stage-tidy`** → `.dca-factory/runs/<story>/tidy.md`: the refactor half of red–green–refactor,
   inside this story's footprint, with every test green and no test changed. A stage that changes
   nothing and says why is finished, not skipped.
8. **gate `tidy`** — the same checks as the build gate, run again: the stage's whole claim is that
   nothing it touched changed what the code does.
9. **`stage-judge`** → `.dca-factory/runs/<story>/judge.md`. Hand it what its skill names as input —
   the story, the plan, `tests.md`, `build.md` and `.dca-factory/evidence/<story>/story.diff`, which
   the end mark of the stage before wrote — never "the tree against HEAD": the diff is the story's,
   HEAD may hold more. The file carries one of three verdicts:
   - `pass` — done, go to the report.
   - `changes-requested` — back to `stage-build` with the confirmed defects, then gate `build`
     again; the round counter applies.
   - `story-conflict` — the story or the plan is wrong. **Stop.** This never goes back to
     `stage-build`: a correction that changes an agreed criterion belongs in the story, and a
     human decides it. Say which criterion conflicts with what.
10. **`stage-document`** → `.dca-factory/runs/<story>/document.md`: the glossary, the context map
   and the project's reader documentation follow what the story changed.
11. **gate `document`** — every stage of this pass wrote its file after the one before it, the judge
   passed it, the story is the one that was planned, every file, path and identifier the stage claims
   exists, and every claim says how it was checked. A story whose documents still describe yesterday
   is not delivered. Where the profile's `acceptance:` applies, the gate does not deliver yet: it
   writes an acceptance record and exits **3** — a question to a human, not a refusal; count no
   round. Stop, and name in the report what to look at (the record lists it) and `/factory-decisions`
   to answer. "Accepted" delivers the story at the next document gate; a correction goes into the
   same story, which runs again from plan.
12. **Report**: first the story's own view, as it is — `bash .agents/factory/factory.sh status --story
   <story> --format md` (passes, stages with their tokens, decisions, and *Next*); do not retell it.
   Then only what that view does not show: the criteria and their tests, what the gate **skipped**,
   and every open assumption from the story. A run that skipped a check must not read as a complete
   verification. The run commits nothing — and a story waiting for acceptance is not ready to
   commit; say what the story's commit holds — the code and tests the stages changed, the story (its
   `status: delivered` line) and its `decisions/`, and — where the project commits its run history —
   `.dca-factory/runs/<story>/` and `.dca-factory/evidence/<story>/` with its hidden files (the red
   ledger, the story digest, the journal). The commit hook checks the index against the working tree,
   so a commit that leaves any of them behind untracked is refused. Then give the checkout back —
   `python3 .agents/factory/factory-cli.py --release` — delivered or stopped alike: a claim nobody
   releases keeps every other worker out until it goes stale (`FACTORY_STALE_AFTER`, two hours).

## Where a run stands

Never decide the next step from memory — read it off the files, so the same story continues
correctly after an interruption, in another session or in another tool:

| State on disk | Next step |
|---|---|
| no `plan.md` | gate `plan`, then `stage-plan` |
| `plan.md`, no `tests.md` | `stage-test` |
| `tests.md`, gate `test` red-and-mapped | `stage-build` |
| `build.md`, gate `build` failing | `stage-build` again (count the round) — the runner does this for every refused gate after its stage |
| `build.md`, gate `build` passing, no `tidy.md` | `stage-tidy` |
| `tidy.md`, gate `tidy` passing, no `judge.md` | `stage-judge` |
| `judge.md` with `changes-requested` | `stage-build` (count the round) |
| `judge.md` with `story-conflict` | stop, escalate to the human |
| `judge.md` with `pass`, no `document.md` | `stage-document`, then gate `document` |
| `document.md`, the story not `status: delivered` | gate `document`; it writes `status: delivered` and `delivered:` into the story when it passes, and only then is the story delivered — the gate is the one writer of that line |
| `document.md`, gate `document` passing | report and stop |
| `.story-digest` differs from the story file | the story changed after it was planned: `stage-plan` again, and every stage after it |
| a stage file journaled before the one before it | it belongs to an earlier pass — a stage ran again (a re-plan, a build after `changes-requested`); that stage file and every later one count as unwritten |
| `.rounds` at 3 | stop, escalate to the human |
| any stage file with a `## needs-human` section | stop; the section names a decision record under `<story>/decisions/` in the story's folder — say which file and what to write into it |
| a decision record for the story is open (no `## Answer`, or one without `by:` and `at:`) | stop — no stage runs while the story waits |
| a decision record is answered and the stage it resumes at (the earlier of `stage:` and the answer's `applies:`) has not cited it | run that stage again; it applies the answer and cites the id (at the plan stage, the plan gate lets exactly this through) |

## Execution tier

Who runs the stages is the human's choice, not yours, and it decides what the run costs and where:

| Asked for | Stages run | Tool processes |
|---|---|---|
| `/factory-run [story]`, "deliver STORY-1", `/loop /factory-run` | **in this session** — a subagent per stage where the tool can start one and it comes back, otherwise in-session | none beyond this session |
| the person runs `factory.sh run [--story X]` in a shell | **the runner**, one process per stage | one per stage |

The runner — `factory.sh run` — is the person's, never yours: it starts a tool process per stage on
top of this session, and refuses to inside one. Asked for "one process per stage", "unattended" or
"in the background", say that this is the runner and that they start it in a shell. Say in the
report which tier ran, and which variant (shared or separate stages).

**Before running a stage in this session, read `reference/execution-tiers.md`** — what each tier
carries, the shared builder and verifier (the default; `reference/shared-stages.md`), the reviews
that run beside each other before the judge, and the stage marks: `factory-cli.py --stage-start
<stage> --story <id>` right before a stage and `--stage-end` right after its file is written, with
the gate called **after** the end mark. Then `reference/running-stages.md` — a defect in a test goes
back to the test stage (`back: test`), what every stage prompt names, and the model per stage.

Rules that hold in every tier:

- A single stage the human asked for (`/stage-build` on a story that already has a plan) is always
  done here — the runner delivers whole stories.
- Degrade rather than wait. A stage is finished when **its file exists**, not when a delegation
  reports success. If a stage you delegated has produced no file when control returns to you, do that
  stage in-session and note the fall-back in the report — a run that stalls waiting for a subagent
  mechanism delivers nothing, and the file contract makes the in-session variant just as correct.
- The runner reads the judge's verdict from the file and acts on it — `changes-requested` goes back
  to the build stage and increments the round counter, `story-conflict` stops the run. In-session
  you do that yourself, from the file rather than from what you remember writing.
- Isolation is a comfort; the gate is the correctness argument. Never skip a gate because a stage
  reported success — a stage judging its own work is exactly what the gate replaces.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type, unless the person asks how to do something
without a session. You may run `factory.sh` for everything that starts no tool — `setup`,
`backlog`, `status`, `decisions`, `update`, `verify`, `check` — but never `run`: it starts a tool
process per stage (`claude -p` and the like) on top of this session, and the runner refuses it
inside one anyway.

## Escalation

Stop the run and hand back to the human when:

- the plan needs a **new bounded context** or a new relationship between contexts — that is a
  structural decision, not a story: a decision record, answered through `/factory-decisions`, which
  also brings the designed map in line;
- a business term in the criteria is neither in the project's glossary nor marked as a proposal;
- three rounds did not converge;
- a stage wrote a `## needs-human` section;
- `stage-judge` returned `story-conflict`;
- a stage would have to add a test framework, a dependency or a build-file change to do its work.

Name the decision, the file it belongs in, and who is asked. Do not decide it yourself. A question
is a **file** — `<story>/decisions/<nn>.md`, named in the stage's `## needs-human` — never a sentence
in a report; how it is written, answered and applied: `reference/running-stages.md`, *A question is
a file*, and `reference/file-contracts.md`, *Decision records*.

## Other kinds of item

`factory-cli.py --story <id> --kind` says what an item is; each kind runs a different subset of the
stages, with the gates, rounds and decisions of a story. Read `reference/story-kinds.md` before one
of these:

- **an adopted story** (`status: adopted`) — behaviour the project already has: plan, test, judge, then
  the adopt gate; nothing is built, every mapped test is green;
- **a journey item** (`kind: journey`) — a guard over delivered stories: plan, test, judge, document;
  its test gate expects the test green;
- **a story delivered by hand** (`--deliver-by-hand`, `--prove`) — never the way to change a
  delivered story: that is a new story;
- **several factories on one backlog** (`claim_remote:`) — claim the story first
  (`factory-cli.py --claim-story <id>`; exit 3: another factory has it, stop and say who);
- **a change outside any story** — `story-gate.py --change` / `--staged` give a direct edit the same
  checks; recommend it, do not invent a story for it.

## A wish instead of a story

What `/factory-run <argument>` means is the gate's to say, not yours: run
`python3 .agents/factory/factory-cli.py --resolve "<argument>"` and follow its one line.

| It prints | Then |
|---|---|
| `story <id>` | run that story, as above |
| `wish` | the argument is a user story in the person's words: hand it to `/factory-backlog`, which drafts the story, asks its fixed questions (which epic, the criteria, run now or keep as a draft) and writes it; once it is released, run the id it names, as above; kept as a draft, stop and say it waits for its release |
| `unknown <word> …` | stop and show the line — the ids the backlog has; a word that names no story is never a new one |
| `backlog` | no argument: work the backlog, below |

## Without a story, and several stories

One story per run; several stories are a loop over it, never two builders working in parallel on
one code base. What comes next is read off the files: `factory-cli.py --listening`, then
`story-gate.py --schedule`, whose last line is `next: <story> <stage>` or `next: none — <why>`.
Deliver what it names exactly as a named story, ask again; on `none` say why, give the checkout back
(`factory-cli.py --release`) and end the turn — never wait or poll inside it, never pick a story
yourself. One worker per checkout: `--stage-start` exits 3 when another holds it — stop and say who.

Read `reference/several-stories.md` before working the backlog or more than one story, or
explaining how the runner does: the schedule's states and order, one story with unfinished code per
checkout, the stale claim, listening under a scheduler (`/loop /factory-run`, `factory.sh run
--watch`), the runner's worktrees, `--parallel`, `--keep-going` and `--max-stages`, where
`run --story` starts, what a running stage does (`factory.sh follow`), and what a story cost
(`--usage`, `--story-budget`).

## The factory without a session

`factory.sh up` runs the factory in the background until `down`; `serve` shows it in a browser, and
every press there — or `factory.sh request <kind> …` — writes a request it works before the next
story. A prompt that says *request `<id>` … you run headless* is such a request: read
`reference/requests.md` first.
