---
id: GATE-LEVELS
part: check
kinds:
- story
reports:
- levels
pass: end-user tests only for the happy path and browser-only scenarios
fail: an end-user test for another scenario — integrate it
---

# GATE-LEVELS

**When:** the test gate of a story with an `e2eTest:` command (contract 9 on)

**Why:** an end-user test is the happy path's; the rest runs lower
