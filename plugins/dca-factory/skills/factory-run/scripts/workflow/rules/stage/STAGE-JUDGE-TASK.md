---
id: STAGE-JUDGE-TASK
part: told
stages:
- judge
kinds:
- task
section: Task mode
marked: stage-judge/SKILL.md
order: 12
---

# STAGE-JUDGE-TASK

A `kind: task` claims that nothing an actor sees has changed. Check that claim first: does the diff change an
answer, a page, a stored value, a published event, a refusal? Then it is a story — `story-conflict`, with the
behaviour named. Otherwise judge the change as any other — the perspectives, the plan's `## Files` — and check that
every finding row the task `closes:` is settled by the diff (file and line); a row it names and does not settle is
`major`. There are no criteria to re-check: write `## Criteria re-checked` with `- none: a task`.
