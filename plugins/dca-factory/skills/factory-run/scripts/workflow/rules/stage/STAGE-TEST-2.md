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

2. **One test per criterion, at the plan's level and shape**, with the project's existing frameworks. A scenario's test
   follows its steps: `Given` arranged with the scenario's own values, `When` the one action, `Then` and each `And` an
   assertion. **How** to write a test that holds (fixture, name, an assertion that can turn red, doubles, waits,
   locators) is the testing craft — the skill `carrier.test` names (`testing`), read before the first test.
   - **Change no build file**: a dependency, plugin, source set or runner is a stack decision. Planned shape impossible
     with what is installed → tests file with `## needs-human` naming the missing runner (decision record,
     `stage: test`), stop. Never install it; never drop silently to a unit test asserting less.
   - `browser:` other than `none` → an end-user test drives the browser (`e2e-testing`). Never read the page's script or
     markup as text to infer what the browser would do.
