---
id: GATE-COMPILES
part: check
stages:
- test
- build
- tidy
- integrate
- adopt
reports:
- compiles
pass: the profile's `compile:` succeeds
fail: it fails — its output quoted
skip: no `compile:` in the profile
---

# GATE-COMPILES

**When:** every gate that runs tests, and the adopt gate

**Why:** nothing is judged on code that does not build
