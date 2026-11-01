---
id: RUN-WINDOW-1
title: A shared window is checked, not believed
part: decision
stages:
- plan
- test
- build
- tidy
pass: one process runs the window, every stage's file is there, and the runner re-runs each post-gate ("checked, not believed")
fail: a file is missing, the red ledger is empty, or a gate refuses — a round is spent and the run goes back to that stage
goes.fail: again
---

# RUN-WINDOW-1

**When:** the builder stages (plan to tidy) run shared

**Why:** one process carries what one mind would, and the runner checks what it claims
