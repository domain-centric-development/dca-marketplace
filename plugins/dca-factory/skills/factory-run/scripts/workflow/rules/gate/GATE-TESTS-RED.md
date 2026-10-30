---
id: GATE-TESTS-RED
part: check
stages:
- test
kinds:
- story
reports:
- tests-red
pass: every mapped test is red, by its assertion
fail: a test is green before the code, cannot be run alone, or no report shows it ran
skip: no test command
note: a test red by a timeout only
---

# GATE-TESTS-RED

**When:** the test gate of a story

**Why:** a test green before the code exists proves nothing
