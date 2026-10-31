---
id: STAGE-TEST-7
part: told
stages:
- test
section: Do
marked: stage-test/SKILL.md
order: 12
---

# STAGE-TEST-7

7. The gate is your test run (`factory-run/reference/stage-common.md`): a single test while you
   write it — that is where you see the assertion it fails on — then the test gate, never the whole
   suite before it. Confirm two things from its report: the test sources compile, and every new test
   fails **on its assertion**, not on a missing class or a wiring error. A test red for the wrong
   reason proves nothing. In a browser test the first step
   that can be missing is an expectation, not an action: `expect(locator).toBeVisible()` before the
   click or the fill, so a form that does not exist yet fails on the expectation and names what is
   missing. A raw `TimeoutError` from an action is red on the harness — the gate accepts the red and
   notes it, and the build stage learns nothing from it.
