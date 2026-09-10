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
| `depends_on` | story ids that must be delivered first; empty list when none |

Body sections:

- `## Story` — one sentence in the project's own ubiquitous language.
- `## Acceptance criteria` — one `- <key>: <criterion>` line each. Criteria are observable
  end-user behaviour, small enough that one agent run delivers the whole story.
  The **key** is lowercase, hyphenated and names the behaviour (`shows-empty-state`), because it
  is committed: the test stage records it next to the test that proves it. A running number
  would point at nothing once the list is reordered.
- `## Assumptions` — the asynchronous channel to the domain contact: one line per assumption,
  `open:` or `answered:`. An assumption is a question, never a decision the team took itself.

## Brownfield

The contract applies to **new** stories. An existing backlog is not migrated wholesale and
existing tests are not renamed; the gate only ever looks at the story it is called with.

## Empty means green

A project with no backlog is not broken. Every stage says which file to create; nothing fails
on the absence of an artefact. The first story is written, then the pipeline works.
