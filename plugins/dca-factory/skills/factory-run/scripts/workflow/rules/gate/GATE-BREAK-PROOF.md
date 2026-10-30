---
id: GATE-BREAK-PROOF
part: check
stages:
- test
- build
- tidy
- adopt
reports:
- break-proof
pass: the test turns red under its break patch
fail: no break patch, it does not apply, or the test stays green under it
skip: the adoption wrote no test of its own
---

# GATE-BREAK-PROOF

**When:** the adopt gate for the tests the adoption wrote (all with `adopt.breakProof: all`), and the test, build and tidy gates for a test changed after it was seen red

**Why:** a test that was never red proves something only if a break of the code turns it red
