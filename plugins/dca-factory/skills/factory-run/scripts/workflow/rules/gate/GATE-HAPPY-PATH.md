---
id: GATE-HAPPY-PATH
title: A story has exactly one happy-path scenario
part: check
kinds:
- story
- adopt
reports:
- happy-path
pass: there is exactly one `(happy path)` scenario
fail: there is none, or more than one
skip: an adoption tests nothing new
---

# GATE-HAPPY-PATH

**When:** the plan gate of a story runs (contract 9 on)

**Why:** one scenario is the story's happy path, the one end-user test
