# Backlog contract

The backlog is markdown with front matter, one file per item, readable and reviewable
without any tooling. No database, no JSON as the source. A generated `index.json` may exist for
tools; it is derived and gitignored.

It lives beside the project description, under `project/` — what is to be built, written by people
before the code. How it is worked through lives under `.agents/factory/` (the machine's), the
stages' hand-overs under `tasks/`, and what exists and why under `docs/`:

```
project/
  product.md         the product description
  tech.md            the technical decisions
  domain.md          the designed domain (optional)
  backlog/
    <epic>/
      epic.md        the epic
      <story>.md     one story
```

The stack profile's `product:`, `tech:`, `domain:` and `backlog:` name other places; without them
these are the places. There is no fallback to a backlog at the project root: where the gate finds
`backlog/` and nothing under `project/`, it names the move in one line.

## Project description

Two files are mandatory before the first story, a third is optional. They are written with the
person who decides what is built, through the project's description skill (`/factory-setup` uses
it), and changed only through it afterwards — no stage edits them. The headings are fixed in this
spelling so the gate can read them; the text under them is in the project's language.

`product.md`:

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

An epic missing one of `intent`, `goal`, `metric`, `domain_contact` is refused by the gate at
the plan stage. The reason is not bureaucracy: a stage that cannot read the intent invents one.

Body section `## Journey` — optional: the flow through the epic that must never break, the steps as a
user takes them to the outcome event, and why a break would hurt; `open:` while it cannot be said. Its
test is a backlog item of its own (below).

## Story

Front matter:

| Field | Meaning |
|---|---|
| `id` | stable identifier |
| `epic` | the epic's `id`; its `epic.md` must exist |
| `context` | the bounded context the story changes. It must exist on the designed map (`domain.md`), or on the one generated from the code where there is no designed map — a story that would need a new context or a new context relationship is not a story, it is a question about the project description |
| `title` | short name |
| `status` | `draft` while it is still being written, `approved` once a human released it for building, `superseded` when another story replaced it. The gate refuses to plan a `draft` story: the most expensive mistake is well-built wrong code. A project that does not use the field is not blocked — the check is then reported as skipped |
| `depends_on` | story ids that must be delivered first; empty list when none. `[A, B]` and a `- A` list both read. The schedule runs stories in this order, ties by id; an unknown id or a cycle blocks the story and is named |

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
    they are what turns a range or a default into a question someone answers;
  - **lines**: one `- <key>: <criterion>` line each, the shorter form.

  Criteria are observable end-user behaviour, small enough that one agent run delivers the whole
  story. They are specification, not executable feature files: the test stage turns each into one
  test in the project's own runner, at the level the plan gives it.
  **The happy path** (contract 9): exactly one scenario per story is marked `(happy path)` —
  `#### <key> (happy path)`, or `- <key> (happy path): <criterion>` — the one that shows what the
  story is for. It gets the end-to-end test; every other scenario is tested integrated, below the
  page, unless the plan gives it `browser-only` with a reason. The plan gate refuses a story with no
  mark or two; the test gate refuses an end-user test for any other scenario.
  Each criterion is behaviour the system does not show yet — its test is red until the build
  stage, and the gate refuses one that is green before it. Behaviour that must keep working is
  what the existing tests guard; it is not a criterion.
  The **key** is lowercase, hyphenated and names the behaviour (`shows-empty-state`), because it
  is committed: the test stage records it next to the test that proves it. A running number
  would point at nothing once the list is reordered.
- `## Out of scope` — optional: one line per behaviour the story deliberately does not deliver,
  with the story or the reason that owns it. The plan does not plan it; the judge reports a change
  that implements it.
- `## Changed expectations` — optional: when the story changes behaviour the system already has,
  one line per expectation that no longer holds, in the project's language (what is seen now, what
  is seen after). No story ids, no file names — nobody has to know which story or which hand wrote
  a test. Released with the story, it is the human's authority for the plan to change the tests
  that follow from it; without it, a plan that finds such tests asks. A human's correction at
  acceptance lands here too, in the same story, when it takes back something the story delivered.
- `## Assumptions` — the asynchronous channel to the domain contact: one line per assumption,
  `open:` or `answered:`. An assumption is a question, never a decision the team took itself.

## Journey item

`kind: journey` in a story's front matter makes it a guard over delivered stories instead of new
behaviour: one scenario walking the epic's `## Journey` to its outcome event, `depends_on:` the stories
that build the steps (required — it becomes ready when they are delivered), no happy-path mark. It runs
plan, test, judge and document — nothing to build — and its test must be **green** at the test gate,
where a story's must be red. Its tests live where `test.journey:` runs them; a later story that changes
a step lists the journey test under `## Changed tests`, as any other.

## Brownfield

The contract applies to **new** stories. An existing backlog is not migrated wholesale and
existing tests are not renamed; the gate only ever looks at the story it is called with.

## Empty means green

A project with no backlog is not broken. Every stage says which file to create; nothing fails
on the absence of an artefact. The first story is written, then the pipeline works.
