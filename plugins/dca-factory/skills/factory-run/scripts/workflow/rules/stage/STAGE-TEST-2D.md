---
id: STAGE-TEST-2D
part: told
stages:
- test
section: Do
marked: stage-test/SKILL.md
---

# STAGE-TEST-2D

2d. **Every test starts from a state it sets itself, and asserts an element.** A suite that shares one application
   and one store empties what its tests write before each test — the base class does it, through the reset the
   profile's `reset:` names, the end-user suite included; a scenario that begins "the list is empty" is then
   true. An assertion names what it is about — a selector, a role, a field, a row — never the page's whole
   text: `contains("disabled")` is true whenever any element is disabled. A test of a criterion above the unit
   level runs through the real input port, except at the plan's `integration (adapter: …)` level; the test gate
   refuses the double (`tests-real`).
