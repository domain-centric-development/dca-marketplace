---
id: GATE-OUTCOME-RAISED
title: A story's code raises its epic's outcome event
part: check
kinds:
- story
reports:
- outcome
pass: the event is declared and raised in what the story changed
fail: the event is not declared, not raised, or raised only outside the story's files
---

# GATE-OUTCOME-RAISED

**When:** the document gate runs for a story that `publishes:` an event (contract 14 on)

**Why:** the epic's outcome event is raised by this story's code
