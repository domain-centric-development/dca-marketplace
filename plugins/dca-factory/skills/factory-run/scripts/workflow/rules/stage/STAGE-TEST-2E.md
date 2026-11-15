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

2e. **Every assertion could fail.** The gate shows each new test red on its first failing assertion only. So **one
   break probe per `## Clauses` row**: the smallest production change violating that clause alone must turn that line's
   assertion red. One no probe turns red is asserted too weakly — sharpen it before the gate. What keeps an assertion
   green whatever the code does (a condition around it, an absence checked before the page reacted, a mechanism the code
   does not use, test data a swap would not notice): the testing craft.
