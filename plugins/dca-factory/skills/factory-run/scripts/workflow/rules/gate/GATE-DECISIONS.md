---
id: GATE-DECISIONS
part: check
reports:
- decisions
pass: every answered record is applied by its stage and stamped
fail: a `## needs-human` without a record, a record open or a draft, or an answer its stage did not apply or cite
note: no record, or an answer a later stage applies
ask: a stage writes a decision record and stops
goes.ask: stop
---

# GATE-DECISIONS

**When:** every gate

**Why:** a question is a record a person answers, and an answer lands where it is cited
