---
id: GATE-OUTCOME
part: check
kinds:
- story
reports:
- outcome
pass: every published event stands in the epic's metric
fail: an event the epic's `metric:` does not name
---

# GATE-OUTCOME

**When:** the plan gate of a story that `publishes:` an event (contract 14 on)

**Why:** the event a story raises is the one its epic measures
