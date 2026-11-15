---
id: STAGE-INTEGRATE-5
part: told
why: a resolution step chased failing tests across files, the build stage's work and not a merge's
stages:
- integrate
section: Do
order: 5
---

# STAGE-INTEGRATE-5

5. Edit nothing outside the conflicted files (or, sent back for a test, the files named). A test the merged code fails is
   the integrate gate's finding for the build stage; do not chase it.
