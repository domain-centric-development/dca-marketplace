---
id: GATE-PIPELINE
part: check
reports:
- pipeline
pass: no stage touched `.agents/factory/`
fail: a stage changed the installed pipeline — put it back
---

# GATE-PIPELINE

**When:** every gate after the plan

**Why:** a stage that changes the gate changes what it is checked by
