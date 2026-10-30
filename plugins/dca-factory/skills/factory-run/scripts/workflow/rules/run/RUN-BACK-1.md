---
id: RUN-BACK-1
part: decision
stages:
- build
fail: a round, and the run goes back to the test stage
goes.fail: test
---

# RUN-BACK-1

**When:** the build stage writes `back: test`

**Why:** a test that cannot pass for its own code goes back to its stage, without a person
