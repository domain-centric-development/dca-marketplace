# Backlog contract

The backlog is markdown with front matter, one file per item — an epic's `epic.md`, a story's `story.md` in a folder of its own — readable and reviewable
without any tooling. No database, no JSON as the source. A generated `index.json` may exist for
tools; it is derived and gitignored.

It lives beside the project description and the living spec, under `product/` — what is to be built and what
holds, written by people before the code (the spec's scenarios by the gate that delivers). The installed pipeline lives under `.agents/factory/`, a run's protocol under
`.dca-factory/runs/`, and what exists and why under `docs/`:

```
dca-factory.profile.yaml   the stack profile
dca.profile.yaml           the method's configuration: the places below and the conventions
product/
  overview.md              the product description
  tech.md                  the technical decisions
  domain.md                the designed domain (optional)
  spec/                    what holds — changed only through deliveries (below)
    journeys.md            flows across contexts, each with its test line
    <context>/
      scenarios.md         the rules and criteria that hold, each with its test line
      glossary.md          the context's language
  discovery/<topic>/       research and proposed epics
  epics/
    <epic>/
      epic.md              the epic
      <story>/             one story, a folder named after its id
        story.md           the story — with its state: draft | approved | delivered | adopted | superseded
        decisions/         its questions (<nn>.md) and acceptances (accept-<n>.md)
        findings.md        the judge's confirmed minors, written when it is delivered
```

Stories stay with their epic for life; they never move between folders. *Backlog* is a view:
`factory.sh backlog` lists every story with its state and the next one that can run — approved, not
delivered, its dependencies met. The stack profile's `product:`, `tech:`, `domain:`, `epics:` and
`runs:` name other places; without them these are the places. An older layout — `product/backlog/`,
a profile under `.agents/factory/`, records under `.agents/factory/decisions/`, run artefacts under
`tasks/` — is named by the gate and moved once by `factory.sh update`; nothing reads it as a fallback.

## Project description

Two files are mandatory before the first story, a third is optional. They are written with the
person who decides what is built, through the project's description skill (`/factory-setup` uses
it), and changed only through it afterwards — no stage edits them. The headings are fixed in this
spelling so the gate can read them; the text under them is in the project's language.

`overview.md`:

| Heading | Says |
|---|---|
| `## What and for whom` | the product in two or three sentences, and its actors |
| `## Surfaces` | how each actor reaches it — pages, notifications, an API, a tool — and on which devices |
| `## How it works` | the main flow across epics; where state lives and what is persisted |
| `## Look and feel` | style direction, language, accessibility level, a design system or styling approach |
| `## Qualities` | security and authorisation stance, privacy, performance, availability, as the product needs them |
| `## Not part of the product` | what it deliberately will not do |

`tech.md`:

| Heading | Says |
|---|---|
| `## Stack` | language, framework and build tool |
| `## Frontend approach` | server-rendered pages, a client application or none — and what that excludes |
| `## Persistence` | where state is kept and how, and what the product does not use |
| `## Runtime` | where and how it runs |
| `## Integrations` | the external systems it talks to |
| `## Version policy` | how dependencies are chosen and kept current |

`domain.md` — the designed cut: the bounded contexts with their responsibility and subdomain type,
and the relationships with pattern, translation and reason. The map generated from the code
(`contextMap:`) shows what was built; a difference between the two is a finding. The plan gate reads
the designed map first, so a story for a context that is designed and not built yet passes.

Decisions only, never code design: "the server stores what is submitted" belongs in the product
description, "server-rendered pages, no client framework" in the technical one, an endpoint or a
package in neither. A heading with nothing to decide gets one honest line, never a placeholder. The
gate (`story-gate.py --project`) reports a missing file as a note and fails a key that names no file
and a file with a heading missing or empty (text in HTML comments does not count).
`factory-backlog` writes no epic and no story while either mandatory file is missing or incomplete,
and reads all three before it writes one. An epic's intent must fit the product it belongs to.

## Epic

Front matter, every field non-empty; the gate refuses an epic without `intent`, `goal`, `metric` or
`domain_contact`:

| Field | Meaning |
|---|---|
| `id` | stable identifier, also the folder name |
| `title` | short name |
| `intent` | why the epic exists — the problem, not the solution |
| `goal` | what changes for the user when it is delivered |
| `metric` | the **outcome event** that measures it: a domain or integration event whose publication in production is the evidence. Not a story count, not a burndown |
| `domain_contact` | who answers domain questions for this epic |

Optional: `discovery` — the report the epic came from (`product/discovery/<topic>/discovery.md`, written by
`factory-discover`); the gate refuses a link to a report that is not there.

Optional: `depends_on` — the epics that must be delivered before this epic's stories start, by id; `[]` or no
line for none. An epic is delivered when it has stories and every one of them is delivered or superseded. The
schedule holds a story of a dependent epic as `blocked` and names the epic it waits for; between epics without
one, the earlier epic — in this order, then by id — goes first, and where the runner runs more than one story
they run side by side. The gate refuses an epic that names no epic there is, itself, or a cycle.

An epic missing one of `intent`, `goal`, `metric`, `domain_contact` is refused by the gate at
the plan stage. The reason is not bureaucracy: a stage that cannot read the intent invents one.

Body section `## Journey` — optional: the flow through the epic that must never break, the steps as a
user takes them to the outcome event, and why a break would hurt; `open:` while it cannot be said; `- none: <why>`
when the epic decides against a journey test. Its test is a backlog item of its own (below). An epic whose
stories are all delivered and that has no journey item is shown as *delivered, unguarded* — unless it said `none:`.

## Story

Front matter:

| Field | Meaning |
|---|---|
| `id` | stable identifier, unique in the whole project — the run folder and the decision records are named after it, and the schedule keys stories by it; a second story with the same id is refused, naming both files |
| `epic` | the epic's `id`; its `epic.md` must exist |
| `context` | the bounded context the story changes. It must exist on the designed map (`domain.md`), or on the one generated from the code where there is no designed map — a story that would need a new context or a new context relationship is not a story, it is a question about the project description |
| `title` | short name |
| `status` | `draft` while it is still being written, `approved` once a human released it for building, `adopted` when it describes behaviour the project already has — adopted, never built (below) — `superseded` when another story replaced it, `delivered` once the document or the adopt gate passed it — and where the runner gave the story a worktree, once the integrate gate put it on the main line — or once a person delivered it by hand (`delivered_by: hand:<who>`, below). Built or adopted, a delivered story reads `status: delivered` (one end state). The person writes `draft → approved`; `→ delivered` is the gate's, or a person's who delivered by hand; a reopen or `--prove` takes it back. The gate refuses to plan a `draft` story: the most expensive mistake is well-built wrong code. A project that does not use the field is not blocked — the check is then reported as skipped |
| `delivered` | the UTC time the story was delivered, written with `status: delivered`. The story's digest leaves it out |
| `delivered_by` | who claims the delivery (contract 18): `gate`, written by the gate that delivered it, or `hand:<who>`, written by a person who built it by hand (`factory-cli.py --deliver-by-hand <story> --by <who>` writes the three lines). A claim, not a proof: the files are the person's. `factory-cli.py --prove <story>` turns a hand's claim into a gate's delivery through the adopt path. The story's digest leaves it out |
| `publishes` | optional (contract 14): the epic's outcome event, on the story after which it can happen — the step that completes the flow. Its name is a word of the epic's `metric:` (the plan gate's `outcome`); at the document gate the production code declares a type of that name and a file the story changed — the aggregate that raises it, or the use case that publishes it — refers to it (`outcome`). One event, or a list |
| `depends_on` | story ids that must be delivered first; empty list when none. `[A, B]` and a `- A` list both read. The schedule runs stories in this order, ties by their epic's place (its `depends_on:`, then its id) and then by id; an unknown id or a cycle blocks the story and is named |

Body sections:

- `## Story` — one sentence in the project's own ubiquitous language.
- `## Acceptance criteria` — in one of two forms, mixable:
  - **scenarios** (the default for a new story): `#### <key>` followed by `- Given`, `- When`,
    `- Then`, `- And`, `- But` steps, grouped under `### Rule: <text>` headings where the story has
    business rules — Gherkin's own shape, written as Markdown:

    ```markdown
    ### Rule: A value the service does not know is not applied

    #### unknown-value-is-rejected
    - Given the input is shown
    - When the user submits a value the service does not know
    - Then the message "…" is shown at the input
    - And no value is applied
    ```

    The gate refuses a rule without a scenario, a scenario without exactly one trigger (an `And`
    after the `When` is a second one; two triggers are two scenarios) or without a `Then`, a step
    outside a scenario, an unknown step and a key used twice. Concrete values belong in the steps:
    they are what turns a range or a default into a question someone answers. Every limit a rule names
    has a scenario on each side of it — the limit accepted, the first value past it refused;
  - **lines**: one `- <key>: <criterion>` line each, the shorter form.

  Criteria are observable end-user behaviour, small enough that one agent run delivers the whole
  story. They are specification, not executable feature files: the test stage turns each into one
  test in the project's own runner, at the level the plan gives it.
  **The happy path** (contract 9): exactly one scenario per story is marked `(happy path)` —
  `#### <key> (happy path)`, or `- <key> (happy path): <criterion>` — the one that shows what the
  story is for. It gets the end-to-end test; every other scenario is tested integrated, below the
  page, unless the plan gives it `browser-only` with a reason. The plan gate refuses a story with no
  mark or two; the test gate refuses an end-user test for any other scenario.
  **The title** (contract 9): a scenario may carry `Title: <text>` on the line under its heading; without
  it the title is the key in words (`shows-empty-state` → "Shows empty state"). An end-user test carries
  the title verbatim as its display name — the test gate checks it — so two implementations of one story
  name the test alike, and a report names the scenario it proves. Where a project keeps a shared list of
  scenario titles its end-user tests are bound to, the `Title:` is that list's title.
  Each criterion is behaviour the system does not show yet — its test is red until the build
  stage, and the gate refuses one that is green before it. Behaviour that must keep working is
  what the existing tests guard; it is not a criterion.
  The **key** is lowercase, hyphenated and names the behaviour (`shows-empty-state`), because it
  is committed: the test stage records it next to the test that proves it, and the living spec keeps
  it for good — a key is unique within its context and names one behaviour of it. A running number
  would point at nothing once the list is reordered.
- `## Out of scope` — optional: one line per behaviour the story deliberately does not deliver,
  with the story or the reason that owns it. The plan does not plan it; the judge reports a change
  that implements it.
- `## Changed expectations` — optional: when the story changes behaviour the system already has,
  one line per expectation that no longer holds, in the project's language (what is seen now, what
  is seen after). No story ids, no file names, no keys — nobody has to know which story or which hand
  wrote a test or a criterion: the plan finds which criteria of the spec the story changes or removes.
  Released with the story, it is the human's authority for the plan to change what holds and the tests
  that follow from it; without it, a plan that finds such a change asks. A human's correction at
  acceptance lands here too, in the same story, when it takes back something the story delivered.
- `## Assumptions` — the asynchronous channel to the domain contact: one line per assumption,
  `open:` or `answered:`. An assumption is a question, never a decision the team took itself. When an answer
  to a decision record is applied, the gate writes it here as `- answered: <the chosen option's text, or the
  answer verbatim> (<record id>)`; a correction at acceptance writes the same line. The line corrects the story
  so far that it can be carried out — it is no requirement of its own; an answer that changes behaviour
  changes a criterion.

## Journey item

`kind: journey` in a story's front matter makes it a guard over delivered stories instead of new
behaviour: one scenario walking the epic's `## Journey` to its outcome event, `depends_on:` the stories
that build the steps (required — it becomes ready when they are delivered), no happy-path mark. It runs
plan, test, judge and document — nothing to build — and its test must be **green** at the test gate,
where a story's must be red. Its tests live where `test.journey:` runs them; a later story that changes
a step lists the journey test under `## Changed tests`, as any other.

## Task

`kind: task` in a story's front matter makes it a change no actor sees: a refactoring, a judge's finding that
changes no behaviour, a dependency or build change, a unit test for an invariant that already holds. It has **no**
acceptance criteria — a criterion is behaviour, and behaviour that changes is a story with a red test; the plan gate
refuses a task with one. What it does stands in the body, in a sentence or two. `closes:` names the finding rows it
settles, `<story>#<n>` (the row's number in that story's `findings.md`), each open; the delivering gate sets them to
`done`. It runs plan, build, tidy, judge and document — no test stage —, and its evidence is the existing suite: the
build and tidy gates run every test command the profile declares, whole, with the architecture and format checks; a
test that existed before the task may not change (`tests-kept`), a new one may be added. No spec delta: what holds is
what held. Taking a feature away is not a task — an actor sees it gone — but a story whose criterion is the absence.

## Adopted story

`status: adopted` describes behaviour the project already has. The factory never builds it; it adopts it:
plan, test and judge map every scenario to a test that exists and is **green**, a test the adoption writes
itself (a *characterization* test, listed under `## Characterization` in `tests.md`) comes with a break —
`.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`, a minimal change to the production code that turns exactly
this test red — and the adopt gate applies each break to a scratch copy, requires red, and delivers the
story (`status: delivered`, `delivered:` and `delivered_by: gate` go into the story — `adopted` was its input,
"the code exists: check it, build nothing", and a delivered story reads the same, built or adopted). The working tree is never touched. `adopt.breakProof: all` in the
profile asks for a break for every mapped test, not only the written ones. A story is adopted whole or not
at all: the adoption writes the tests that are missing. A `depends_on` on an adopted story is met once it
is delivered; afterwards its tests are guarded like any delivered story's.

## Delivered by hand

A story a person built — by hand, with another tool, where the factory never ran — is delivered by hand:
`status: delivered`, `delivered:` (UTC) and `delivered_by: hand:<who>`, written by hand or by
`factory-cli.py --deliver-by-hand <story> --by <who>`, committed with the trailer `Story: <id>`. The views
read it as **delivered, claimed**; the schedule never runs it. `factory-cli.py --prove <story>` sets it
`status: adopted` and removes the three lines (the claim is kept in the story's evidence as `claim`); the adopt
path then checks it — every criterion on a green test, a break for every test it writes, a fresh judge — and the
adopt gate delivers it with `delivered_by: gate`. A delivered story is not delivered a second time: a change of
delivered behaviour is a new story with `## Changed expectations`.

## The living spec

A story is a change; `product/spec/` (the configuration's `spec:`) holds what is true today, per bounded context
and feature: `<spec>/<context>/<feature>/scenarios.md` for each feature — a term of the context's language with a
glossary entry of `**Type:** Feature`, named as the code's package would spell it (`productdetails`) — and
`<spec>/<context>/scenarios.md` for what belongs to no feature. `<context>` is the story's `context:`, lowercase,
words joined by `-`; `<feature>` its `feature:` (none: the context's own file). A story names at most one feature —
criteria of several are several stories. Every file carries the criteria that hold, in the story's own shape: a scenario under its `### Rule:`, or a
line; criteria without a rule before the first rule. No status, no ticks, no happy-path mark, no story id.
Under each criterion one `Test: <selector>` line, written by the gate alone from the story's `tests.md`; a
criterion without one, or with a red test, is unproven, readable without the factory. Journeys stand in
`<spec>/journeys.md`, keyed by the flow; a `kind: journey` item merges there. `glossary.md` beside a
context's scenarios is its language, kept by the glossary skill and the document stage — the one file under
`spec/` a skill writes.

- **The delta.** The plan stage reads the context's spec and writes `## Spec delta` in `plan.md`:
  `- adds <key>`, `- changes <key>`, `- holds <key>` (word for word what the spec has), `- removes <key>: <why>`,
  `- rule "<old>" → "<new>"`, `- adds feature <name>` for a feature the context does not have yet, and
  `- moves <key>: <from> → <to>` for a criterion that stands under another feature (`context` for none). What
  follows from comparing story and spec — the moves and the new feature included — the skeleton writes; a
  removal and a renamed rule only the plan can say. Keys are unique across the context's files, so a move keeps
  its key.
- **The check** (test gate, `spec-delta`): every key named agrees with what the comparison says, a removed
  key stands in the spec, a renamed rule leaves no criterion under its old text, and every change or removal
  of what holds is backed by the story's `## Changed expectations` or an answered decision — otherwise the
  plan stage asks. Keys are unique per context: a new key the spec holds otherwise is a change.
- **The merge**, when the story is delivered — after its acceptance where the profile asks for one: the
  document gate, the adopt gate, or in a story's worktree the integrate gate, which checks the delta again
  against the main line as it stands (a criterion another story changed meanwhile is a refusal). Added,
  replaced, removed, renamed by key; a rule left without a criterion goes. A rule's criteria the story lists stand
  together in the story's order, held ones included — where the first of them stood under that rule, else at the
  rule's end — so the order follows the story that delivered them last, not the order they arrived in. A test of the spec this story
  renamed or moved goes under `tests.md`'s `## Moved tests` (`| <key> | <Class>#<method> |`); the delivering
  gate refuses a spec test line that names a test no longer there (`spec-tests`).
- **By hand.** `--deliver-by-hand` merges a story's new criteria without test lines; a story that changes
  what holds needs a plan to derive its delta — `--prove` runs it through the adopt path.
- **Agreement.** `factory-cli.py --spec-check` names every criterion of a delivered story that is not in its
  spec, unless a later story removed it. Whether a criterion came from a story is not asked: a delivered
  story is history and may be gone; the spec holds.

Which stories are delivered, by the gate or by a hand, and which are open follows from the front matter
alone — `grep -l '^status: delivered' …/story.md`, `grep -h '^delivered_by:'` — without the factory.

## Brownfield

The contract applies to **new** stories. An existing backlog is not migrated wholesale and
existing tests are not renamed; the gate only ever looks at the story it is called with.

## Empty means green

A project with no backlog is not broken. Every stage says which file to create; nothing fails
on the absence of an artefact. The first story is written, then the pipeline works.
