---
id: STAGE-BUILD-NOT1
part: told
why: a test that could never pass because of its own locator stopped the story for a human decision nobody needed
stages:
- build
section: Do not
order: 11
---

# STAGE-BUILD-NOT1

- Never change a test to make it pass (`GATE-TESTS-KEPT`, `GATE-RED-PROOF`); a test unable to pass because of its own code (helper, locator, fixture, page object) while its assertion stays right → finding in build.md (test, line, why, how you showed the code meets the scenario) and a line `back: test` — the test stage repairs it.
