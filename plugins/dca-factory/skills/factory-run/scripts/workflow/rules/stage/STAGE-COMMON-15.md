---
id: STAGE-COMMON-15
part: told
why: a test broken by its own helper stopped the story for a human, though it could be repaired without changing what it asserts
section: One session, several stages
order: 15
---

# STAGE-COMMON-15

- With build in the stages: a test that cannot pass for a reason in its own code (a helper, a locator), not in what it
  asserts → write `build.md` with the finding first, go back to the test stage in this session (repair without
  changing what it asserts, write its break, run the test gate), then build again. Changing what a test asserts stays
  a needs-human question.
