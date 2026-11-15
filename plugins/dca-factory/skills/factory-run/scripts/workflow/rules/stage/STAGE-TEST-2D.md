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

2d. **Every test starts from a state it sets itself**: a suite sharing one app and store empties what its tests write
   before each test — the base class does it through the profile's `reset:`, end-user suite included. Above unit level
   a criterion's test runs through the real input port, except the plan's `integration (adapter: …)`; the gate refuses
   the double (`tests-real`). Other fixture rules (own values, visible, minimal, a helper that asserts its arrangement
   worked): the testing craft.
