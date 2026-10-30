---
id: GATE-FILES-LISTED
part: check
reports:
- files-listed
pass: the hand-over lists every file the stage changed
fail: no `## Files`, or a changed file missing from it
skip: the stage's changes were not recorded
note: a listed path the stage did not change
---

# GATE-FILES-LISTED

**When:** the gates of the stages that list their files (test, build, tidy)

**Why:** the judge and the next stage read the list, not the tree
