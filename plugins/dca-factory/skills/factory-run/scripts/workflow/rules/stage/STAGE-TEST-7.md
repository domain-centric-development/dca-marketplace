---
id: STAGE-TEST-7
part: told
why: a test red on a missing class or a harness timeout counted as a red proof that proved nothing
stages:
- test
section: Do
order: 12
---

# STAGE-TEST-7

7. The gate is your test run (what every stage is told): a single test while you write it — that is where you see
   the assertion it fails on — then the test gate, never the whole suite before it. Confirm two things from its
   report: the test sources compile, and every new test fails **on its assertion**, not on a missing class or a
   wiring error. A test red for the wrong reason proves nothing; a raw timeout from a browser action is red on the
   harness — the gate accepts it and notes it, and the build stage learns nothing from it (in a browser test the
   first step that can be missing is an expectation: the `e2e-testing` craft).
