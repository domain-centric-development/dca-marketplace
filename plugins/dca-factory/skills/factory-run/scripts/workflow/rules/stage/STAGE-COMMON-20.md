---
id: STAGE-COMMON-20
part: told
why: a test whose own code could not pass had no stage allowed to repair it, so a human was asked
section: A repeat round
order: 20
---

# STAGE-COMMON-20

- *The build stage sent the story back*: `build.md` names a defect in a test's own code — the test
  stage repairs exactly that, without changing what the test asserts, and writes the test's break
  (see the contract).
