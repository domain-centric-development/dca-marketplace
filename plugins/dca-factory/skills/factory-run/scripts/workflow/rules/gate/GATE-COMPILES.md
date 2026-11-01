---
id: GATE-COMPILES
title: The code compiles before it is judged
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
fail: `compile:` fails — its output is quoted
skip: the profile has no `compile:`
---

# GATE-COMPILES

**When:** a gate that runs tests runs, or the adopt gate runs

**Why:** nothing is judged on code that does not build
