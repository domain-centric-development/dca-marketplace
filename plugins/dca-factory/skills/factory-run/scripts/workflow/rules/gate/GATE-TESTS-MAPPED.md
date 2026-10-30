---
id: GATE-TESTS-MAPPED
part: check
reports:
- tests-mapped
pass: every criterion has a test, and no row names another
fail: the table is unreadable, a criterion has no test, or a row names a criterion the story lacks
---

# GATE-TESTS-MAPPED

**When:** every gate that runs tests

**Why:** a criterion without a test is one no gate can fail on
