---
id: GATE-TESTS-GREEN
title: A criterion is met when its test, seen red, is green
part: check
kinds:
- story
- journey
- adopt
reports:
- tests-green
pass: every mapped test is green and was seen red (a journey's or adoption's needs no red)
fail: a test is red, or green without ever having been red
skip: a test is green, but nothing proves it ever failed
---

# GATE-TESTS-GREEN

**When:** the build, tidy or integrate gate runs, or the test gate of a journey or adoption runs

**Why:** a criterion is met when its test, seen red before, is green
