---
id: STAGE-COMMON-15
part: told
section: One session, several stages
marked: factory-run/reference/stage-common.md
---

# STAGE-COMMON-15

- Where the stages include build: if a test cannot pass for a reason in its own code (a helper, a
  locator), not in what it asserts, write `build.md` with the finding first, then go back to the test
  stage in this session — repair the test without changing what it asserts, write its break, run the
  test gate — and build again. A change to what a test asserts stays a needs-human question.
