---
id: GATE-INVARIANTS
part: check
stages:
- test
- adopt
kinds:
- story
- adopt
reports:
- invariants
pass: every invariant the plan names has its own unit test in tests.md's `gate:invariants` table
fail: a domain type without an `## Invariants` line, no table, a row that does not fit, or a rule untested
---

# GATE-INVARIANTS

**When:** the test gate of a story (contract 13 on) or an adoption (24 on)

**Why:** every rule of a domain type gets a unit test of its own, beside the criteria
