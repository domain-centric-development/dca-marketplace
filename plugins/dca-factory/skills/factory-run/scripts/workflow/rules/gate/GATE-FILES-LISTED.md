---
id: GATE-FILES-LISTED
title: A hand-over lists every file the stage changed
part: check
reports:
- files-listed
pass: the hand-over lists every file the stage changed
fail: there is no `## Files`, or a changed file is missing from it
skip: the stage's changes were not recorded
note: a listed path is one the stage did not change
---

# GATE-FILES-LISTED

**When:** a gate of a stage that lists its files runs (test, build, tidy)

**Why:** the judge and the next stage read the list, not the tree
