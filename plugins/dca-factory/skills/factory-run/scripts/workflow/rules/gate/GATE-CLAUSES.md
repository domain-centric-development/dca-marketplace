---
id: GATE-CLAUSES
title: Every clause is asserted at a fitting level
part: check
kinds:
- story
reports:
- clauses
pass: every clause names the assertion that holds it, at a fitting level
fail: there is no `gate:clauses` table, a clause has no line, a line names no assertion, or a state clause sits at adapter level
---

# GATE-CLAUSES

**When:** the test gate runs for a story with `Then`/`And` clauses (contract 15 on)

**Why:** each clause is asserted somewhere a reader can find it
