---
id: STAGE-TIDY-NOT1
part: told
why: a tidy-up could weaken or delete a test while every gate stayed green
stages:
- tidy
section: Do not
order: 9
---

# STAGE-TIDY-NOT1

- Never change what a test asserts, delete a test or weaken an assertion (`GATE-TESTS-KEPT`).
