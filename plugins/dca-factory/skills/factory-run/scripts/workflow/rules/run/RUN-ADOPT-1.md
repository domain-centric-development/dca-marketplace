---
id: RUN-ADOPT-1
title: An adoption ends at its own gate
part: decision
stages:
- adopt
pass: the adopt gate passes — the story is delivered, or integrated from its worktree
fail: the adopt gate refuses — a round is spent and the run goes back to the test stage
goes.fail: test
---

# RUN-ADOPT-1

**When:** the judge of an adopted story passed

**Why:** an adoption ends at its own gate
