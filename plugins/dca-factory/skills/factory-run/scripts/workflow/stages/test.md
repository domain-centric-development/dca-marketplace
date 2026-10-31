---
name: test
order: 2
hand_over: tests.md
window: builder
kinds:
- story
- journey
- adopt
traits:
- gated
- post_gated
- tested
- red
- lists
- in_order
sizes:
- plan.md
- tests.md
---

# test

Writes a test per criterion at the level the plan gives it, plus unit tests for the invariants, and records the criterion-to-test table; the tests are red before any production code is written. Its skill: `stage-test`.
