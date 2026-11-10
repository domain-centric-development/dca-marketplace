---
id: STAGE-COMMON-10
part: told
why: one session carrying several stages could skip a stage gate and hand an unchecked state to the next
section: One session, several stages
order: 10
---

# STAGE-COMMON-10

- After the test, build and tidy stages run that stage's gate — the command the prompt names, with
  `--stage <stage> --brief` — and fix exactly what it names before the next stage, at most three
  attempts per stage.
