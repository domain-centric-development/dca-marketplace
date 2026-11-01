---
id: GATE-TESTS-COMMITTED
title: Every mapped test is in the story's commit
part: check
reports:
- tests-committed
pass: every mapped and spec-named test file is in the story's commit as it is
fail: a test file is missing from the commit, or differs from it (an ignored one included)
---

# GATE-TESTS-COMMITTED

**When:** the integrate gate runs

**Why:** a test that is not in the commit proves nothing on the main line
