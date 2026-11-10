---
id: STAGE-BACKLOG-4
part: told
why: delivered stories each passed alone while the walk through all their steps to the outcome had no guard
section: Journey item
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/backlog-contract.md
---

# STAGE-BACKLOG-4

`kind: journey` in a story's front matter makes it a guard over delivered stories instead of new
behaviour: one scenario walking the epic's `## Journey` to its outcome event, `depends_on:` the stories
that build the steps (required — it becomes ready when they are delivered), no happy-path mark. It runs
plan, test, judge and document — nothing to build — and its test must be **green** at the test gate,
where a story's must be red. Its tests live where `test.journey:` runs them; a later story that changes
a step lists the journey test under `## Changed tests`, as any other.
