---
id: STAGE-BUILD-NOT1
part: told
stages:
- build
section: Do not
order: 11
---

# STAGE-BUILD-NOT1

- Do not change a test to make it pass. **A test that cannot pass because of its own code** — a
  helper, a locator, a fixture, a page object that can never find what the page renders — while what
  it asserts stays exactly as it is, is not yours to repair and not a human's to decide: write the
  finding in `build.md` (the test, the line, why it cannot pass, and how you showed that the code
  meets the scenario) and a line `back: test` on its own; the round goes to the test stage, which
  repairs the test and proves with a break that it still bites.
