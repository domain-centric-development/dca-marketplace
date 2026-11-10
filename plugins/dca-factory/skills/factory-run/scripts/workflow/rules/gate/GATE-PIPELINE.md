---
id: GATE-PIPELINE
title: A stage leaves what judges it as it is
part: check
reports:
- pipeline
pass: no stage touched `.agents/factory/`, and every guarded path the story changed is one its plan announced
fail: a stage changed the installed pipeline, or a guarded path the plan did not announce — the stage puts it back
---

# GATE-PIPELINE

**When:** a gate after the plan runs

**Why:** a stage that changes what decides its gate — the gate itself, the stack profile, the rule selection of the architecture suite, the commit hook — changes what it is checked by; the gate is evidence only while nothing it reads is in the judged stage's reach
