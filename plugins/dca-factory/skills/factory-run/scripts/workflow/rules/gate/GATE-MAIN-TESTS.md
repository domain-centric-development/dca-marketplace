---
id: GATE-MAIN-TESTS
title: A merge resolution leaves the main line's tests alone
part: check
reports:
- main-tests
pass: the resolution changed no test the main line holds
fail: the resolution changed a main-line test — its side is put back
note: a test is taken as adapted to a rename, or waived by an answer
---

# GATE-MAIN-TESTS

**When:** the integrate gate runs after a merge with conflicts

**Why:** the main line's tests are its own; a resolution keeps them
