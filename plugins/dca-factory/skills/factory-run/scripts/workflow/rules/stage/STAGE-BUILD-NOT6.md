---
id: STAGE-BUILD-NOT6
part: told
why: a build rewrote the plan after the tests to answer a gate, and the delivery sent the story a round back
stages:
- build
- tidy
section: Do not
order: 16
---

# STAGE-BUILD-NOT6

- Do not change plan.md. Whatever a gate asks of the plan once the tests are written goes into build.md: a domain
  type's invariants under `## Invariants`, a planned file you took back under `## Plan changes` with why
  (`- `<path>` — <why>`). The gates read it beside the plan (`plan-kept`).
