---
id: STAGE-PLAN-TASK
part: told
stages:
- plan
kinds:
- task
section: Task mode
order: 18
---

# STAGE-PLAN-TASK

A `kind: task` changes nothing an actor sees, and has no criterion. The plan says what changes in the code and why
no behaviour does: `## Context`, `## Changes`, `## Files` (with `changes: new` and `changes: removed` where a file
comes or goes) and `## Invariants` only where a domain type changes; no `## Acceptance criteria`, no levels, no
`## Spec delta`, no `## Changed tests` — a test that existed before stays as it is, except that it follows a type or
a method the task renames: that is no question and no `## needs-human`, the plan lists the file under `## Files` with
`changes: follows the renamed <old> → <new>`, and the gate reads the rename from the tree. Name the finding rows the story's
`closes:` settles and where each one sits. Where the change would alter behaviour after all — an answer, a page, a
stored value — stop with a `## needs-human`: it is a story, not a task.
