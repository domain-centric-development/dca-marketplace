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

7. Run a single test while writing it (see what it fails on), then the test gate — never the whole suite first. Confirm
   from its report: sources compile, and each new test fails **on its assertion**, not on a missing class or wiring. Red
   for the wrong reason proves nothing. A raw browser timeout is red on the harness — accepted and noted, but useless to
   the build; in a browser test the first step that can be missing is an expectation (`e2e-testing`).
