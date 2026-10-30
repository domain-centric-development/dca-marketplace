---
id: GATE-SPEC-DELTA
part: check
stages:
- test
- integrate
reports:
- spec-delta
pass: the delta adds and holds — nothing that holds changes, or every change is backed
fail: the delta does not fit the spec, or changes what holds without `## Changed expectations` or an answer
---

# GATE-SPEC-DELTA

**When:** the test gate, where the plan targets a spec

**Why:** what holds changes only where a person backed the change
