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

5. Edit nothing outside the conflicted files — or, sent back for a test, outside the files named. A test that the merged code would now fail is the integrate
   gate's finding and goes back to the build stage; this step does not chase it.
