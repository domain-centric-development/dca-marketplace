---
id: GATE-RED-PROOF
title: A green test is the version that was seen red
part: check
reports:
- red-proof
pass: no test changed since it was recorded red, or changed on an answer
fail: a test changed since its red proof — the test stage records it red again
goes.fail: test
skip: the ledger has no digests (an older one)
---

# GATE-RED-PROOF

**When:** a gate that expects green runs (build, tidy; test for a journey or adoption), with a red ledger

**Why:** a green test proves something only as the version that was seen red
