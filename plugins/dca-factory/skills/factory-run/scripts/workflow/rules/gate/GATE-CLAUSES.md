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

A clause about what is stored holds through the input port with the real store, never in an adapter test whose
input ports are stubs. A form field that holds what the person entered is no such clause — a word says so, or
every quoted text and number it names stands in the scenario's `When`: the page shows the request's input again,
which is the incoming adapter's own translation.
