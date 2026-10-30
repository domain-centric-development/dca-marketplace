---
id: GATE-OUTCOME-RAISED
part: check
kinds:
- story
reports:
- outcome
pass: the event is declared and raised in what the story changed
fail: not declared, not raised, or raised only outside the story's files
---

# GATE-OUTCOME-RAISED

**When:** the document gate of a story that `publishes:` an event (contract 14 on)

**Why:** the epic's outcome event is raised by this story's code
