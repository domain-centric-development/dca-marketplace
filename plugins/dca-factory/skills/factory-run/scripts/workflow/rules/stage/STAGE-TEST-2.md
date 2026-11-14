---
id: STAGE-TEST-2
part: told
why: a test stage added a dependency or a runner to make its planned shape possible, a stack decision no story owns
stages:
- test
section: Do
order: 2
---

# STAGE-TEST-2

2. Write **one test per criterion, at the level the plan gave it** — for a scenario, the test follows its steps:
   `Given` the arrangement, with the scenario's own values, `When` the one action, `Then` and each `And` after it an
   assertion — in the shape the plan named, with the test frameworks the project already has. **How** to write a
   test that holds — the fixture, the name, an assertion that can turn red, doubles, waits, locators — is the
   testing craft: the skill the profile's `carrier.test` names (`testing`), read before the first test. What
   follows here is what the gate and the pipeline read.
   **Change no build file**: adding a dependency, a plugin, a source set or a runner is a stack decision, not part
   of a story. If the planned shape is impossible with what is installed, write the tests file with a
   `## needs-human` section naming the missing runner and stop — do not install it, and do not silently drop to a
   unit test that asserts less. The section names a decision record with `stage: test` (the shape, and the
   citation of an answered record: what every stage is told).
   Where the profile names a browser runner (`browser:` other than `none`), an end-user test of a page drives the
   browser — the browser craft is the `e2e-testing` skill the testing craft points to. Never read the page's
   script or markup as text to infer what the browser would do.
