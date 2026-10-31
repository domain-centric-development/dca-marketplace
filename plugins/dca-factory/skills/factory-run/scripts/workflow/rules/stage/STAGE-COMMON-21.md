---
id: STAGE-COMMON-21
part: told
section: A repeat round
order: 21
---

# STAGE-COMMON-21

- *The story's tests changed after the test stage saw them fail* (the main line was merged into the story's
  branch): the test stage records each named test as it now is — red where the code before the story fails it,
  else its break (see the contract) — and changes nothing it asserts. A stale red proof is never a question.
