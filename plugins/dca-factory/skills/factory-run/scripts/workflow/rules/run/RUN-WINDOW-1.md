---
id: RUN-WINDOW-1
part: decision
stages:
- plan
- test
- build
- tidy
pass: one process for the window; every stage's file there, each post-gate re-run by the runner ("checked, not believed")
fail: a file missing, the red ledger empty, or a gate refusing — a round and back to that stage
goes.fail: again
---

# RUN-WINDOW-1

**When:** the builder stages (plan to tidy) run shared

**Why:** one process carries what one mind would, and the runner checks what it claims
