---
id: STAGE-BUILD-NOT2
part: told
why: an expectation that cannot hold is a question about the story, and settling it in the build hides that question
stages:
- build
section: Do not
order: 12
---

# STAGE-BUILD-NOT2

- **A test whose expectation cannot hold** (assertions excluding each other, a substring that also matches what must be
  there) is a question about the story, not a deviation: `## needs-human` with a decision record, `stage: build`, naming
  test, line and why; stop. Answered (and the test repaired where it says) → build again, cite the id in build.md.
