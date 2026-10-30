---
id: GATE-PLAN-ADOPTS
part: check
kinds:
- story
reports:
- plan-adopts
pass: every row names a criterion and a test that is there
fail: a row names no criterion or a missing test, or a split would leave the story without its happy path
---

# GATE-PLAN-ADOPTS

**When:** the plan gate of a story whose plan has `## Adopt` rows

**Why:** what already holds is adopted with its test, never built again
