---
id: RUN-ROUNDS-1
title: A story converges in three rounds or stops
part: decision
stages:
- test
- build
- tidy
- document
- adopt
- integrate
fail: the gate refuses — a round is spent and the run goes back to the refused stage (or an earlier one the story's files need); at three rounds the story stops (exit 1)
goes.fail:
- again
- stop
---

# RUN-ROUNDS-1

**When:** a gate refuses after its stage

**Why:** a story converges in a few rounds or a person looks
