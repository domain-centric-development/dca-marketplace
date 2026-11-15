---
id: STAGE-PLAN-TASK
part: told
why: a change meant to touch no behaviour could alter an answer or a stored value without becoming a story
stages:
- plan
kinds:
- task
section: Task mode
order: 18
---

# STAGE-PLAN-TASK

`kind: task`: no actor-visible change, no criterion. The plan: `## Context`, `## Changes`, `## Files` (`changes: new` /
`changes: removed`), `## Invariants` only where a domain type changes; no criteria, levels, `## Spec delta` or
`## Changed tests`. An existing test stays, except following a type or method the task renames — no question: list the
file with `changes: follows the renamed <old> → <new>`; the gate reads the rename from the tree. Name the finding rows
`closes:` settles and where each sits. Behaviour would change after all (an answer, a page, a stored value) →
`## needs-human`: it is a story.
