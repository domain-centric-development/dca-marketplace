---
id: STAGE-TIDY-1
part: told
stages:
- tidy
section: Do
order: 1
---

# STAGE-TIDY-1

1. Read the plan and the build file, then the code they name. Work **only inside this story's
   footprint**: the files the build stage changed, and what it made demonstrably redundant — a
   helper nothing calls any more, a duplicate the new code introduced, and what the plan's `## Files`
   lists beyond the story's own code — an old wording, a last caller's target, a twin check. The
   story's test files and the test support they use are footprint too. A smell elsewhere is a note in
   your file, never an edit.
