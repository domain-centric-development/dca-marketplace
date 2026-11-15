---
id: STAGE-BUILD-NOT6
part: told
why: a build rewrote the plan after the tests to answer a gate, and the delivery sent the story a round back
stages:
- build
section: Do not
order: 16
---

# STAGE-BUILD-NOT6

- Never change plan.md. What a gate asks of the plan once tests exist goes into build.md: a domain type's invariants
  under `## Invariants`, a planned file taken back under `## Plan changes` (`- `<path>` — <why>`) — read beside the plan
  (`plan-kept`).
