---
id: STAGE-INTEGRATE-3
part: told
why: a merge resolution dropped test cases another story had added on the main line
stages:
- integrate
section: Do
order: 3
---

# STAGE-INTEGRATE-3

3. A test file the main line changed keeps the main line's side whole (`git show <target>:<file>`), this story's cases beside them — never drop, merge away or rewrite a case the story did not write, however alike (`GATE-MAIN-TESTS`; a missing line restarts this step naming it: put it back, edit nothing else, add the file's row). Exception: a main-line call to what this story re-signed or removed cannot compile — rewrite that call to the new signature, keep the rest.
