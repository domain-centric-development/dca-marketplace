---
id: GATE-SUITE
title: A change keeps the whole suite green
part: check
stages:
- build
- tidy
- integrate
reports:
- suite
- flaky
- test
pass: every required suite ran tests and none was red
fail: a suite is red, a required key has no command, or no report shows a run
skip: `required:` names no test command
note: a red test outside the story is green alone — it is flaky
---

# GATE-SUITE

**When:** the build, tidy or integrate gate runs, for the suites `required:` names, or a task's gate runs every test command

**Why:** a change keeps the whole suite green, not just its own tests
