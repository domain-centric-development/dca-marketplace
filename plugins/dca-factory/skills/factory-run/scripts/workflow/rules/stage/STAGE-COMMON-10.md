---
id: STAGE-COMMON-10
part: told
why: one session carrying several stages could skip a stage gate and hand an unchecked state to the next
section: One session, several stages
order: 10
---

# STAGE-COMMON-10

- After test, build and tidy: run that stage's gate (the prompt's command, `--stage <stage> --brief`), fix exactly what
  it names, at most three attempts, before the next stage.
