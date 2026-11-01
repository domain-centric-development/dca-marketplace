---
id: GATE-BREAK-PROOF
title: A test that was never red turns red under a break
part: check
stages:
- test
- build
- tidy
- adopt
reports:
- break-proof
pass: the test turns red under its break patch
fail: there is no break patch, it does not apply, or the test stays green under it
skip: the adoption wrote no test of its own
---

# GATE-BREAK-PROOF

**When:** the adopt gate checks the tests the adoption wrote (all of them with `adopt.breakProof: all`), or the test, build or tidy gate checks a test changed after it was seen red

**Why:** a test that was never red proves something only if a break of the code turns it red
