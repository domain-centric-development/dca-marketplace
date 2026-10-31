---
id: STAGE-INTEGRATE-1
part: told
stages:
- integrate
section: Do
order: 1
---

# STAGE-INTEGRATE-1

1. Read the story and its plan, then every file the conflicts list names. Between `<<<<<<<` and `=======` is
   the story's side, between `=======` and `>>>>>>>` the main line's. `git log --oneline -5 <target>` and
   `git diff <target>...HEAD -- <file>` show what each side meant.
