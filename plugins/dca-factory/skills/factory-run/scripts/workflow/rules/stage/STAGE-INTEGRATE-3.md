---
id: STAGE-INTEGRATE-3
part: told
stages:
- integrate
section: Do
marked: stage-integrate/SKILL.md
---

# STAGE-INTEGRATE-3

3. A test the main line changed keeps the main line's side whole. Every case, assertion and helper line another
   story added to a test file stays as the main line has it — `git show <target>:<file>` shows it — and this story's
   own cases go beside them. A test case the story did not write is never yours to drop, merge away or rewrite,
   even where the two sides look alike. The runner holds the resolution to it (`main-tests`: every line the main
   line added to a test since the story began is still there) and, where one is missing, starts this step again
   with the file and the lines named: put them back, edit nothing else, and add the file's row to `integrate.md`.
   One exception: a main-line line that calls what this story re-signed or removed in production code cannot
   compile as it was — rewrite that call to the story's signature and keep the rest of its case; the check takes
   such a line as adapted when the file still has it in a like form, and names it.
