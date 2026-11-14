---
id: STAGE-TEST-2D
part: told
why: tests started from state other tests left, swallowed refusals in their setup, or asserted on a page's whole text
stages:
- test
section: Do
order: 6
---

# STAGE-TEST-2D

2d. **Every test starts from a state it sets itself.** A suite that shares one application and one store empties what
   its tests write before each test — the base class does it, through the reset the profile's `reset:` names, the
   end-user suite included. A test of a criterion above the unit level runs through the real input port, except at
   the plan's `integration (adapter: …)` level; the test gate refuses the double (`tests-real`). The fixture's other
   rules — values of its own, visible and minimal, a helper that asserts its arrangement succeeded — are the
   testing craft's.
