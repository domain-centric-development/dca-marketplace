---
id: STAGE-TEST-4
part: told
stages:
- test
section: Do
marked: stage-test/SKILL.md
---

# STAGE-TEST-4

4. Place tests where this project places tests. Look at the existing layout and follow it —
   source set, folder, naming, base classes, test data builders. Do not introduce a second
   convention next to the project's own. **Before you write a helper, a page-object call or a
   context setup, find the existing one** — in the base classes, the page objects, the other tests of
   the same level — and call it. Where the same code stands in two places already, the third use
   extracts it into the shared test support (a base class, a builder, a page object) and calls it from
   there; the test support is yours to change, the tests that existed before keep what they assert.
