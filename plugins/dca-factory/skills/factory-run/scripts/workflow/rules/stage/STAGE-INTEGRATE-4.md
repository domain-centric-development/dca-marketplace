---
id: STAGE-INTEGRATE-4
part: told
why: a conflict marker left in a file would reach the merged commit
stages:
- integrate
section: Do
order: 4
---

# STAGE-INTEGRATE-4

4. Remove every conflict marker. A file with one left is refused, and the integrate gate searches every file
   the story's commit changes.
