---
id: STAGE-TIDY-1
part: told
why: a tidy-up reached into code outside the story and buried its change among unrelated edits
stages:
- tidy
section: Do
order: 1
---

# STAGE-TIDY-1

1. Read plan and build.md, then the code they name. Work **only inside the story's footprint**: files the build changed,
   what it made demonstrably redundant (a helper nothing calls, a duplicate the new code introduced), what the plan's
   `## Files` lists beyond the story's code (an old wording, a last caller's target, a twin check), the story's test files
   and their test support. A smell elsewhere is a note, never an edit.
