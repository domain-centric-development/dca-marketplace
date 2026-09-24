---
name: factory-run
description: Runs one backlog story through the delivery pipeline — plan, test, build, tidy, judge, document — with a deterministic story gate between the stages, and several stories in dependency order. Use when the user asks to deliver, implement or run a story or ticket end to end ("run story X", "deliver US-3", "/factory-run"), to work through the backlog ("run the backlog", "deliver everything that is ready", "/factory-run" without a story), to keep a session working on the backlog as it fills, or to set up the pipeline in a project that has none. Reads the backlog, the stack profile and the hand-over files — no project knowledge of its own.
---

# Run one story

You are the orchestrator. You own the order of the stages, the file contracts between them, the
gate calls and the escalation. You do **no** domain work yourself: no plan, no test, no
production code, no review verdict. That belongs to the stage assignments below, and keeping
them apart is what makes a run reproducible.

## What the run needs

| Thing | Where | Missing? |
|---|---|---|
| the story | `backlog/<epic>/<story>.md` | offer to write one from the templates and stop |
| the epic | `backlog/<epic>/epic.md` | same |
| the stack profile | `.agents/factory/factory.profile.yaml` | create it from the template by detecting the build (see below) |
| an architecture the gate can check | the project's rule suite and building blocks | this is **not** the pipeline's job: the project installs it once with its DCA bootstrap skill, and the factory calls that skill rather than owning it. Without one, the build gate skips the architecture check and names it |
| the gate | `.agents/factory/story-gate.py` | the installer writes it (step 1 below) |
| the commit guard | `.githooks/pre-commit` | the installer writes it and sets `core.hooksPath` (step 1 below) |

Read `reference/backlog-contract.md` for the backlog format and `reference/file-contracts.md`
for what each stage reads and writes. Both are part of this skill.

An empty project is not an error. Nothing here fails because an artefact does not exist yet —
say precisely which file to create, create it when the user agrees, then continue.

## First run in a project

0. Check that the project has an architecture to gate on — a rule suite and the building blocks its
   code implements. If it has none, ask the developer to run the project's DCA bootstrap skill
   first; it also settles the facts the profile needs (build commands, source sets, conventions).
   The factory delivers stories, it does not install an architecture: one is a once-per-project
   step that belongs to the method, the other repeats per story. The installer says so and installs
   the pipeline anyway, so a project can adopt the two in either order.
1. Run the pipeline's installer from this skill's folder, for the tool you are:
   `bash <this skill's folder>/scripts/factory.sh install --tool <claude|codex|opencode>`, and report
   what it printed. It starts no tool. It puts the gate and the runner under `.agents/factory/`, the
   commit hook under `.githooks/`, `.gitattributes`, the pipeline's section in `AGENTS.md` and, for
   Claude Code, the gate's permission and a SessionStart hook; it writes the stack profile from
   what it detects. The hook runs the same checks the gate does: tool hooks and deny rules do not
   port between agent tools, but every tool commits through git, so that is where the guard
   belongs.
2. Check the stack profile the installer wrote (`.agents/factory/factory.profile.yaml`, from
   `templates/factory.profile.yaml.tmpl`), and add the `required:` line with what the human says
   must hold for every change. Where a command is wrong or missing, fix it there.
   **Detect, do not assume:** look at what the project actually has — a Gradle wrapper, a Maven
   wrapper, a `*.sln`/`*.csproj`, a `package.json` — and fill in the commands from it. Two
   worked examples, not defaults to copy blindly:

   ```yaml
   # Gradle, JUnit, end-user tests in their own source set
   compile: ./gradlew testClasses
   test: ./gradlew test
   e2eTest: ./gradlew test-e2e
   filterFlag: --tests
   filterFormat: "{class}.{method}"
   architecture: ./gradlew test-architecture
   format: ./gradlew spotlessCheck
   #knowledge: <the skill that answers from a catalog, with citations>
   #carrier.test: <skill>              # optional: who carries a stage's craft
   #reviews: security                  # optional: perspectives beyond the built-in three
   #review.security: <review skill>     # optional: who carries a perspective
   ```

   ```yaml
   # .NET, xUnit
   compile: dotnet build
   test: dotnet test
   e2eTest: dotnet test
   filterFlag: --filter
   filterFormat: "FullyQualifiedName~{class}.{method}"
   ```

   ```yaml
   # Python, pytest — tests are functions in a module, selected by file
   test: python3 -m pytest -q --junitxml=test-results/pytest.xml
   covers.test: "**"
   filterFormat: "{file}::{method}"
   ```

   Leave a command out when the project has none. The gate then skips that check and names it —
   which is honest, whereas gating on a command that does not exist turns governance off after
   the second red run.
3. Adding a capability later means one more line in the profile, not an edit to any stage: a
   formatter under `format:`, a rule suite under `architecture:` (both run by the build gate), a
   further review perspective under `reviews:`, the reviewer for an existing perspective under
   `review.<perspective>:` (both read by `stage-judge`), or the skill that carries a stage's craft
   under `carrier.<stage>:` (read by that stage).

## The run

Call the gate as `python3 .agents/factory/story-gate.py --story <id> --stage <plan|test|build|tidy|document>`
from the project root. Exit code 0 means proceed; any `gate:fail` line stops the stage that was
about to run, and the fix belongs to the stage that produced the artefact, not to you.

1. **gate `plan`** — refuses an incomplete epic, a story without a context or criteria, a story
   still in `draft`, and a context that is not on the project's context map. It also reports when
   the project's instruction file is past the size a tool loads, since the rest is truncated in
   silence. Do not
   repair the backlog yourself beyond obvious typos; an epic without an intent is a question for
   the story's `domain_contact`.
2. **`stage-plan`** → `tasks/<story>/plan.md`
3. **`stage-test`** → `tasks/<story>/tests.md`
4. **gate `test`** — every criterion mapped, test sources compile, every mapped test red. A
   mapped test that is already green means the criterion is not new behaviour or the test asserts
   nothing; send it back to `stage-test`.
5. **`stage-build`** → `tasks/<story>/build.md`
6. **gate `build`** — every mapped test green, and the profile's `architecture:` and `format:`
   commands succeed. Both run in the gate, not on a stage's word. On failure, hand the gate output back to
   `stage-build`. Every repeat round — this one, a refused gate after any stage, a judge's
   `changes-requested` — increments `tasks/<story>/.rounds`; at **three** the run
   stops and escalates. The counter is a file, not something you remember — an in-session run has
   no other honest way to count, and a resumed run must see the same number.
7. **`stage-tidy`** → `tasks/<story>/tidy.md`: the refactor half of red–green–refactor, inside
   this story's footprint, with every test green and no test changed. A stage that changes nothing
   and says why is finished, not skipped.
8. **gate `tidy`** — the same checks as the build gate, run again: the stage's whole claim is that
   nothing it touched changed what the code does.
9. **`stage-judge`** → `tasks/<story>/judge.md`, which carries one of three verdicts:
   - `pass` — done, go to the report.
   - `changes-requested` — back to `stage-build` with the confirmed defects, then gate `build`
     again; the round counter applies.
   - `story-conflict` — the story or the plan is wrong. **Stop.** This never goes back to
     `stage-build`: a correction that changes an agreed criterion belongs in the story, and a
     human decides it. Say which criterion conflicts with what.
10. **`stage-document`** → `tasks/<story>/document.md`: the glossary, the context map and the
   project's reader documentation follow what the story changed.
11. **gate `document`** — every file, path and identifier the stage claims exists, and every claim
   says how it was checked. A story whose documents still describe yesterday is not delivered.
12. Report: the story, the criteria and their tests, what the gate checked, what it **skipped**,
   and every open assumption from the story. A run that skipped a check must not read as a
   complete verification.

## Where a run stands

Never decide the next step from memory — read it off the files, so the same story continues
correctly after an interruption, in another session or in another tool:

| State on disk | Next step |
|---|---|
| no `plan.md` | gate `plan`, then `stage-plan` |
| `plan.md`, no `tests.md` | `stage-test` |
| `tests.md`, gate `test` red-and-mapped | `stage-build` |
| `build.md`, gate `build` failing | `stage-build` again (count the round) — the runner does this for every refused gate after its stage |
| `document.md` without `.delivered` | gate `document`; it writes `.delivered` when it passes, and only then is the story delivered |
| `.story-digest` differs from the story file | the story changed after it was planned: `stage-plan` again, and every stage after it |
| `build.md`, gate `build` passing, no `tidy.md` | `stage-tidy` |
| `tidy.md`, gate `tidy` passing, no `judge.md` | `stage-judge` |
| `judge.md` with `changes-requested` | `stage-build` (count the round) |
| `judge.md` with `story-conflict` | stop, escalate to the human |
| `judge.md` with `pass`, no `document.md` | gate `document` is next after `stage-document` |
| `document.md`, gate `document` passing | report and stop |
| `.rounds` at 3 | stop, escalate to the human |
| any stage file with a `## needs-human` section | stop; the section names a decision record under `.agents/factory/decisions/` — say which file and what to write into it |
| a decision record for the story is open (no `## Answer`, or one without `by:` and `at:`) | stop — no stage runs while the story waits |
| a decision record is answered and its `stage:` still ends in `## needs-human` | run that stage again; it applies the answer and cites the id (at the plan stage, the plan gate lets exactly this through) |

## Execution tier

Who runs the stages is the human's choice, not yours, and it decides what the run costs and where:

| Asked for | Stages run | Tool processes |
|---|---|---|
| `/factory-run [story]`, "deliver STORY-1", `/loop /factory-run` | **in this session** — a subagent per stage where the tool can start one and it comes back, otherwise in-session | none beyond this session |
| the person runs `factory.sh run` or `backlog` in a shell | **the runner**, one process per stage | one per stage |

The runner — `factory.sh run` and `backlog` — is the person's, never yours: it starts a tool process
per stage on top of this session, and refuses to inside one. Asked for "one process per stage", "unattended" or "in the
background", say that this is the runner and that they start it in a shell. Say in the report which
tier ran.

- **subagent per stage**: the stage gets the story and its predecessor file as its whole input and a
  fresh context of its own — the isolation the runner gives, without a process per stage.
- **in-session** where the tool has no subagents: you carry out the stage assignment yourself, in
  order, reading only the story and the predecessor file for that stage — not what you remember
  from earlier stages. The file contract plus the gate is what keeps this honest.
- **the runner**: it calls the tool once per stage, and each stage process sees only the project —
  its skills, the carriers the profile names, its settings — not the person's plugins or MCP
  servers, with one prefix shared by every stage. So every stage begins with an empty context by
  construction; it applies the gates, the judge's verdict, the round counter and the file checks
  itself, and records each stage's cost with its price. Per-tool flags (a model, an effort level, a
  sandbox) come from the environment — `FACTORY_CLAUDE_ARGS`, `FACTORY_CODEX_ARGS`,
  `FACTORY_OPENCODE_ARGS` — because they are the tool's configuration and never the process's.

**Plan to tidy in one context — only when asked.** The person may ask for the builder stages to share
a context ("shared builder", `factory.sh run --shared-builder`, `FACTORY_SHARED_BUILDER=1`); it is off
otherwise, every run. In the runner, one process then carries plan, test, build and tidy and runs each
stage's gate itself; the runner checks that the red proof exists and runs the build and tidy gates
again. In a session, the same variant is one subagent for plan to tidy, running the gate after each
stage and stopping on a refusal it cannot fix in three attempts. In both, the judge and the document
stage keep a fresh context of their own, and every stage still writes its own file, so the story can
be resumed stage by stage. It costs less — the stages build on what the one before read — and it gives
up one thing: build knows how the tests were written. Say in the report which variant ran.

**A model per stage.** The profile may name one: `model.<tool>.<stage>`, or `model.<tool>` for
every stage. The runner passes it as the tool's model flag. In the subagent tier, start the stage's
subagent on that model where the tool lets a subagent take one (Claude Code's subagents take an
alias such as the ones the profile names; a full model name the subagent tool does not accept runs
on the session's model). In-session the model cannot change. `--stage-start` records the request
either way, and the status shows a stage whose model is not the one requested — so a request that
had no effect is visible, not assumed.

In the subagent and in-session tiers, mark every stage so its cost is known: run
`python3 .agents/factory/story-gate.py --stage-start <stage> --story <id>` right before it and
`--stage-end <stage> --story <id>` right after its file is written. The gate records the window in
the story's journal and reads the tool's own session log for it later — Claude Code's log of this
session, subagents included, or Codex's — so `--usage`, the schedule and a budget see in-session
stages the way they see the runner's. A mark without a log it can read records the stage as
unknown. Do not work on anything else between the two marks: the window counts everything the
session did in it.

A single stage the human asked for (`/stage-build` on a story that already has a plan) is always
done here — the runner delivers whole stories.

Degrade rather than wait. A stage is finished when **its file exists**, not when a delegation
reports success. If a stage you delegated has produced no file when control returns to you, do
that stage in-session and note the fall-back in the report — a run that stalls waiting for a
subagent mechanism delivers nothing, and the file contract makes the in-session variant just as
correct.

One thing the runner does that an in-session run cannot: it reads the judge's verdict from the
file and acts on it — `changes-requested` goes back to the build stage and increments the round
counter, `story-conflict` stops the run. In-session you do that yourself, from the file rather than
from what you remember writing.

Isolation is a comfort; the gate is the correctness argument. Never skip a gate because a stage
reported success — a stage judging its own work is exactly what the gate replaces.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type, unless the person asks how to do something
without a session. You may run `factory.sh` for everything that starts no tool — `install`,
`update`, `status`, `usage`, `decisions`, `schedule`, `change`, `parity` — but never `run` or
`backlog`: they start a tool process per stage (`claude -p` and the like) on top of this session,
and the runner refuses them inside one anyway.

## Escalation

Stop the run and hand back to the human when:

- the plan needs a **new bounded context** or a new relationship between contexts — that is a
  scoping decision, not a story;
- a business term in the criteria is neither in the project's glossary nor marked as a proposal;
- three rounds did not converge;
- a stage wrote a `## needs-human` section;
- `stage-judge` returned `story-conflict`;
- a stage would have to add a test framework, a dependency or a build-file change to do its work.

Name the decision, the file it belongs in, and who is asked. Do not decide it yourself.

A question is a **file**, not a sentence in a report: the stage writes
`.agents/factory/decisions/<story>-<nn>.md` from `templates/decision.md.tmpl` — the question, the
options, its recommendation, never an answer — and names it in its `## needs-human` as
`decision: <id>`. That is what makes the question survive the session and reach whoever answers
it, in this session or another (see `reference/file-contracts.md`, *Decision records*). When you
resume a story whose record is answered, run the stage that asked (`stage:` in the record) with
the answer in front of it; the gate checks that its new file cites the id, and stamps the record
applied. The human answers through `factory-decisions` — in this session or another — which lists
the records (`story-gate.py --list-decisions`), explains one and writes `## Answer` only on their
confirmation.

## Outside a story

A direct edit gets the same checks without a story: `python3 .agents/factory/story-gate.py
--change` runs the profile's compile, test, architecture and format commands and fails a required
one (the profile's `required:` line) that is missing, left out or ran no test. `--staged` checks
what a commit contains and refuses when the working tree differs from the index; the commit hook
is that command, and CI runs `--change` on its checkout. Recommend it when someone asks whether a
change is ready to commit — do not invent a story for it. `--parity <config>` checks that several
implementations each prove a scenario contract from their reports (`reference/file-contracts.md`).

## Without a story — work the backlog

`/factory-run` with no story named works the backlog instead of one story:

1. Run `python3 .agents/factory/story-gate.py --listening` — the sign of life a second session sees
   in `/factory-status` while this one waits — then `python3 .agents/factory/story-gate.py
   --schedule`. Its last line is `next: <story> <stage>` or `next: none — <why>`.
2. For `next: <story> <stage>`: deliver that story from that stage, exactly as a named story —
   the gates, the stage marks, the escalations. When it is delivered or stops for a decision, go
   back to 1. Never pick a story yourself; the schedule orders by dependencies and keeps one story
   with unfinished code at a time.
3. For `next: none`: say why in one or two lines — which decision waits (and that it is answered
   through `/factory-decisions`), which story is stopped or running elsewhere, or that the backlog is
   done — give the checkout back (`python3 .agents/factory/story-gate.py --release`) and end the
   turn. Do not wait inside the turn and do not poll: files do not change while you wait.

**One worker per checkout.** `--stage-start` takes the checkout for this session and exits 3 when
another worker holds it — a second session, or a runner. Then stop, say who holds it (the gate prints
it; `/factory-status` too), and end the turn; never work around it. A holder that shows no sign of
life for two hours (`FACTORY_STALE_AFTER`) is taken as stopped, and the next worker takes over.

**Listening on the backlog.** A session that should pick up new stories and answered decisions
by itself in its own context runs this under a scheduler: in Claude Code `/loop /factory-run` (it
wakes, works what is ready, and sleeps again). A second session — or a person — manages meanwhile: writes stories with
`/factory-backlog`, answers questions with `/factory-decisions`, watches with `/factory-status`. It
changes backlog and decision files only, never code; the working session is the one writer. The
same loop outside any session is the runner's `backlog --watch`, which the person starts in a shell.

## Several stories

One story per run; several stories are a loop over it, never agents working in parallel on one
code base. What comes next is read off the files, like everything else:

```
python3 .agents/factory/story-gate.py --schedule
```

prints each story with its state — `delivered` (its document gate passed), `waiting` (an open decision record), `resumable`
(answered, with the stage that asked), `in-progress` (with the stage it continues from: a refused
gate's stage, else the first missing file), `ready`, `stopped` (three rounds, a story conflict, a
refused plan gate, a `## needs-human` without a record), `blocked` (a dependency not delivered,
unknown or on a cycle), `unreleased`/`superseded` — and ends with `next: <story> <stage>` or
`next: none — <why>`. Order: `depends_on`, ties by id.

**One story with unfinished code at a time.** A story that got past its plan stage (it has
`tests.md`) and is not delivered holds the checkout: it is next if it can run, and while it waits
or is stopped no other story starts — the next one would build on its tests and code. A story that
stopped with a question at its plan stage wrote no code, so independent stories run past it.

The runner — the person's, in a shell — does the same loop: `factory.sh backlog [--tool <t>]` runs the next story from the stage the
schedule names, asks again, and ends when nothing can run. A story that stops for a decision does
not end it (`run` exits 3 there); any other stop does, because retrying a failure spends a run on
the same refusal. `--watch` keeps it waiting while a story waits on a human: it re-reads the
schedule every `--interval` seconds (default 60, 1–3600), invokes no agent while nothing changed,
and resumes the answered story at the stage that asked. `--max-stages <n>` caps the agent
invocations of the run (exit 4, the work so far stays); `.agents/factory/stop` ends it before the
next story.

**What a story cost.** The runner asks Claude Code and Codex for their machine-readable output and
records each invocation's tokens — input, cache read, cache write, output, and Claude's cost — as a
`usage` line in the story's journal. `python3 .agents/factory/story-gate.py --usage [--story <id>]`
sums them per story and stage, repeat rounds included; the schedule shows each story's total.
`--story-budget <tokens>` (on `run` and `backlog`) stops dispatch once a story has used that many,
counted from the journal, so a restart or a second session continues the same count; the stage
that crosses the line still finishes, because usage is known only after it ran. A tool that reports
nothing — OpenCode today, a custom `FACTORY_TOOL_CMD` without `FACTORY_USAGE_FORMAT` — is shown as
invocations without a report, never as zero. An in-session run is measured through the stage marks
(above, *Execution tier*); a session log carries tokens but no price, so its cost reads `—`, not 0.
An old session log can be read whole: `story-gate.py --usage-from claude-session|codex-session <log>`. The watch lives as long as its process: a closed session or terminal ends it, and a
file wakes nobody. In-session, do the same loop yourself — ask the schedule, run the story it
names, ask again — and stop instead of waiting.
