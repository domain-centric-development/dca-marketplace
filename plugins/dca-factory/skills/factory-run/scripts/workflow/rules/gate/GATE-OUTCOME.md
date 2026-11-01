---
id: GATE-OUTCOME
title: A story publishes only events its epic measures
part: check
kinds:
- story
reports:
- outcome
pass: every published event stands in the epic's metric
fail: the story publishes an event the epic's `metric:` does not name
---

# GATE-OUTCOME

**When:** the plan gate runs for a story that `publishes:` an event (contract 14 on)

**Why:** the event a story raises is the one its epic measures
