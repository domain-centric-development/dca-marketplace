---
id: GATE-INVARIANTS
title: Every invariant has a unit test of its own
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
fail: a domain type has no `## Invariants` line, there is no table, a row does not fit, or a rule is untested
---

# GATE-INVARIANTS

**When:** the test gate runs for a story (contract 13 on) or an adoption (24 on)

**Why:** every rule of a domain type gets a unit test of its own, beside the criteria
