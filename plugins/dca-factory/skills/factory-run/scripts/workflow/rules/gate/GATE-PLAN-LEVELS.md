---
id: GATE-PLAN-LEVELS
part: check
reports:
- plan-levels
pass: every key of the plan has its level
fail: a key without `level:`
---

# GATE-PLAN-LEVELS

**When:** the test gate

**Why:** every scenario's level is chosen once, in the plan
