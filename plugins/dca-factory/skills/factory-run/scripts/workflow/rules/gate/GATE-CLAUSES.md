---
id: GATE-CLAUSES
part: check
kinds:
- story
reports:
- clauses
pass: every clause names the assertion that holds it, at a fitting level
fail: no `gate:clauses` table, a clause without a line, no assertion there, or a state clause at adapter level
---

# GATE-CLAUSES

**When:** the test gate of a story with `Then`/`And` clauses (contract 15 on)

**Why:** each clause is asserted somewhere a reader can find it
