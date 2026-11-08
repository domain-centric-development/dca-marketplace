---
id: RUN-BACK-1
title: A test that cannot pass goes back to the test stage
part: decision
stages:
- build
fail: a test cannot pass — the build stage asks to go back (`back: test`), a round is spent and the run goes back to the test stage
goes.fail: test
---

# RUN-BACK-1

**When:** the build stage writes `back: test`

**Why:** a test that cannot pass for its own code goes back to its stage, without a person
