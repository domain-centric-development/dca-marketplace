---
id: GATE-TESTS-EXIST
title: Every mapped test is found in its file
part: check
reports:
- tests-exist
pass: the test is found in its file
fail: there is no source file, or the class lacks the method
---

# GATE-TESTS-EXIST

**When:** a gate that runs tests runs, for each mapped test

**Why:** a test that is only a row is indistinguishable from a red one
