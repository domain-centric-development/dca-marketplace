---
id: STAGE-COMMON-12
part: told
why: stages wrote the changed-files list by hand and it disagreed with what the tree had changed
section: One session, several stages
order: 12
---

# STAGE-COMMON-12

- `tests.md`, `build.md`, `tidy.md`: run the files skeleton first, fill the rest, never the list; gate only a filled
  file (`GATE-FILES-LISTED`).
