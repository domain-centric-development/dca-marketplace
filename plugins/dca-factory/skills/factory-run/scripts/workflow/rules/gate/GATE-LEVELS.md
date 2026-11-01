---
id: GATE-LEVELS
title: End-user tests cover only the happy path
part: check
kinds:
- story
reports:
- levels
pass: end-user tests exist only for the happy path and browser-only scenarios
fail: an end-user test exists for another scenario — it has to be integrated
---

# GATE-LEVELS

**When:** the test gate runs for a story with an `e2eTest:` command (contract 9 on)

**Why:** an end-user test is the happy path's; the rest runs lower
