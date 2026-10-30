---
id: GATE-TESTS-GREEN
part: check
kinds:
- story
- journey
- adopt
reports:
- tests-green
pass: every mapped test is green and was seen red (a journey's or adoption's needs no red)
fail: a test is red, or green without ever having been red
skip: green, but nothing proves it ever failed
---

# GATE-TESTS-GREEN

**When:** the build, tidy and integrate gates; the test gate of a journey or adoption

**Why:** a criterion is met when its test, seen red before, is green
