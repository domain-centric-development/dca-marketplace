---
id: STAGE-TEST-2
part: told
stages:
- test
section: Do
marked: stage-test/SKILL.md
order: 2
---

# STAGE-TEST-2

2. Write **one test per criterion, at the level the plan gave it** — for a scenario, the test follows its steps: `Given`
   is the arrangement, `When` the one action, `Then` and each `And` after it an assertion, with the
   scenario's own values — the `Given` arranged with them even where the outcome seems not to depend on
   it (a refusal that answers alike for an empty and a full state still starts from the state the
   scenario names) — in the shape the plan named, using the test
   frameworks the project already has. It asserts the behaviour a user or a caller can observe,
   not the internals. **Change no build file**: adding a dependency, a plugin, a source set or a
   runner is a stack decision, not part of a story. If the planned shape is impossible with what
   is installed, write the tests file with a `## needs-human` section naming the missing runner
   and stop — do not install it, and do not silently drop to a unit test that asserts less. The
   section names a decision record with `stage: test` (the shape, and the citation of an answered
   record: `factory-run/reference/stage-common.md`).
   Where the profile names a browser runner (`browser:` other than `none`), an end-user test of a page drives the browser: use
   the end-user testing craft (the `e2e-testing` skill, or the profile's `carrier.test`) — the
   application started by the test, the fake clock for anything that counts or expires, a stand-in for
   a permission the user answers. Never read the page's script or markup as text to infer what the
   browser would do.
