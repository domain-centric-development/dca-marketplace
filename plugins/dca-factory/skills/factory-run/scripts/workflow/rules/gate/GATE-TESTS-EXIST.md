---
id: GATE-TESTS-EXIST
part: check
reports:
- tests-exist
pass: the test is found in its file
fail: no source file, or the class without the method
---

# GATE-TESTS-EXIST

**When:** every gate that runs tests, for each mapped test

**Why:** a test that is only a row is indistinguishable from a red one
