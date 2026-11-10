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

2e. **Every assertion could fail.** Ask of each one: with the behaviour absent, would it turn red? An assertion on
   a mechanism the code does not use (a flash attribute count where the page renders its message from the
   model), a count of something nothing writes, an absence that holds before the feature exists — each is green
   whatever the code does. So is an assertion inside an `if` (or a loop over a filtered list): when nothing
   meets the condition it asserts nothing. So is an absence checked right after the action without waiting:
   it holds before the page has reacted — wait for the state the action leads to first, then assert what is
   absent (the end-user craft: waits are explicit). Assert the element the criterion names, in the state it
   names: "no message" is the message's element absent from the page the user sees, not an empty map beside it.
   **One break probe per clause.** For each row of `## Clauses`, name the smallest change to the production
   code that violates that clause and leaves the others standing — the message not shown, the value not
   stored, the order reversed — and check that the assertion on that clause's line turns red under it. A
   test stops at its first failing assertion, so its red run proves the first clause only; for new
   behaviour the probe is the red phase taken clause by clause, not test by test. A clause no probe can
   turn red is asserted too weakly: sharpen the assertion before the gate.
   **Test data a swap would turn red.** Where a test passes several numbers or strings of the same type,
   each differs from the others — two quantities, two prices, two names alike let the code mix them up and
   stay green. Cases that can fail apart are tests of their own, not one test looping over them.
