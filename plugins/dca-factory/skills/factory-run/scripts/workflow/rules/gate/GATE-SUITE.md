---
id: GATE-SUITE
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
fail: a suite red, a required key without a command, or a run no report shows
skip: `required:` names no test command
note: a red test outside the story, green alone — flaky
---

# GATE-SUITE

**When:** the build, tidy and integrate gates, for the suites `required:` names; every test command for a task

**Why:** a change keeps the whole suite green, not just its own tests
