---
id: GATE-PIPELINE
title: A stage leaves the installed pipeline as it is
part: check
reports:
- pipeline
pass: no stage touched `.agents/factory/`
fail: a stage changed the installed pipeline — the stage puts it back
---

# GATE-PIPELINE

**When:** a gate after the plan runs

**Why:** a stage that changes the gate changes what it is checked by
