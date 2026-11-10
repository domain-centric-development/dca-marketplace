---
id: STAGE-COMMON-12
part: told
why: stages wrote the changed-files list by hand and it disagreed with what the tree had changed
section: One session, several stages
order: 12
---

# STAGE-COMMON-12

- Before you write `tests.md`, `build.md` or `tidy.md`, run the files skeleton the prompt names: it
  writes the file's list of changed files from the tree (or adds the missing ones to a file you wrote).
  Fill in the rest, never the list, and run the stage's gate only when the file is filled — never on
  the bare skeleton.
