---
id: STAGE-TEST-2E
part: told
why: assertions that could never fail, inside a condition or on an unused mechanism, passed whatever the code did
stages:
- test
section: Do
order: 7
---

# STAGE-TEST-2E

2e. **Every assertion could fail.** The gate shows each new test red on its assertion; it cannot show that every
   clause's assertion bites. So **one break probe per clause**: for each row of `## Clauses`, name the smallest change
   to the production code that violates that clause and leaves the others standing, and check that the assertion on
   that clause's line turns red under it — a test stops at its first failing assertion, so its red run proves the
   first clause only. A clause no probe can turn red is asserted too weakly: sharpen it before the gate. What makes
   an assertion green whatever the code does — a condition around it, an absence checked before the page reacted,
   a mechanism the code does not use, test data a swap would not notice — is listed in the testing craft.
