---
id: GATE-DECISIONS
title: Every answered question is applied by its stage
part: check
reports:
- decisions
pass: every answered record is applied by its stage and stamped
fail: there is a `## needs-human` without a record, a stage's open question names no `tag:` from the factory's list, a record is open or a draft, or an answer was not applied or cited by its stage
note: there is no record, or an answer is one a later stage applies
ask: a stage writes a decision record and stops
goes.ask: stop
---

# GATE-DECISIONS

**When:** a gate runs

**Why:** a question is a record a person answers, and an answer lands where it is cited
