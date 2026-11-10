---
id: STAGE-TIDY-NOT3
part: told
why: a repository-wide formatter run buried the story's change in noise and made the judge's diff unreadable
stages:
- tidy
section: Do not
order: 11
---

# STAGE-TIDY-NOT3

- Do not reformat files the story never touched; a formatter run across the repository buries this
  story's change in noise and makes the judge's diff unreadable.
