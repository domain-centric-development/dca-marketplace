# Backlog contract

The backlog is markdown with front matter, one file per item, readable and reviewable
without any tooling. No database, no JSON as the source. A generated `backlog/index.json`
may exist for tools; it is derived and gitignored.

```
backlog/
  <epic>/
    epic.md          the epic
    <story>.md       one story
```

## Product scope

One file per project, above every epic: `backlog/product.md`, or wherever the profile's
`product:` points. It is written once, before the first story, by `factory-scope` with the person
who decides what is built, and changed only through `factory-scope` afterwards. Six headings, fixed
in this spelling so the gate can read them; the text under them is in the project's language:

| Heading | Says |
|---|---|
| `## What and for whom` | the product in two or three sentences, and its actors |
| `## Surfaces` | how each actor reaches it — pages, notifications, an API, a tool — and on which devices |
| `## How it works` | the main flow across epics; where state lives and what is persisted |
| `## Look and feel` | style direction, language, accessibility level, a design system or styling approach |
| `## Qualities` | security and authorisation stance, privacy, performance, availability, as the product needs them |
| `## Not part of the product` | what it deliberately will not do |

Product decisions only, never code design: "the server stores what is submitted" belongs here, an
endpoint or a package does not. A heading with nothing to decide gets one honest line, never a
placeholder. The gate reports a missing file as a note — a project without one is not blocked —
and fails a `product:` that names no file and a file with a heading missing or empty (text in
HTML comments does not count). `factory-backlog` writes no epic and no story while the file is
missing. An epic's intent must fit the product it belongs to.

## Epic

Front matter, all four fields mandatory and non-empty:

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

## Story

Front matter:

| Field | Meaning |
|---|---|
| `id` | stable identifier |
| `epic` | the epic's `id`; its `epic.md` must exist |
| `context` | the bounded context the story changes. It must exist in the project's context map — a story that would need a new context or a new context relationship is not a story, it is a scoping question |
| `title` | short name |
| `status` | `draft` while it is still being written, `approved` once a human released it for building, `superseded` when another story replaced it. The gate refuses to plan a `draft` story: the most expensive mistake is well-built wrong code. A project that does not use the field is not blocked — the check is then reported as skipped |
| `depends_on` | story ids that must be delivered first; empty list when none. `[A, B]` and a `- A` list both read. The schedule runs stories in this order, ties by id; an unknown id or a cycle blocks the story and is named |

Body sections:

- `## Story` — one sentence in the project's own ubiquitous language.
- `## Acceptance criteria` — one `- <key>: <criterion>` line each. Criteria are observable
  end-user behaviour, small enough that one agent run delivers the whole story.
  Each criterion is behaviour the system does not show yet — its test is red until the build
  stage, and the gate refuses one that is green before it. Behaviour that must keep working is
  what the existing tests guard; it is not a criterion.
  The **key** is lowercase, hyphenated and names the behaviour (`shows-empty-state`), because it
  is committed: the test stage records it next to the test that proves it. A running number
  would point at nothing once the list is reordered.
- `## Changed expectations` — optional: when the story changes behaviour the system already has,
  one line per expectation that no longer holds, in the project's language (what is seen now, what
  is seen after). No story ids, no file names — nobody has to know which story or which hand wrote
  a test. Released with the story, it is the human's authority for the plan to change the tests
  that follow from it; without it, a plan that finds such tests asks.
- `## Assumptions` — the asynchronous channel to the domain contact: one line per assumption,
  `open:` or `answered:`. An assumption is a question, never a decision the team took itself.

## Brownfield

The contract applies to **new** stories. An existing backlog is not migrated wholesale and
existing tests are not renamed; the gate only ever looks at the story it is called with.

## Empty means green

A project with no backlog is not broken. Every stage says which file to create; nothing fails
on the absence of an artefact. The first story is written, then the pipeline works.
