---
id: STAGE-TIDY-7
part: told
why: stages ran the whole suite before the gate ran the same commands, paying twice for one answer
stages:
- tidy
section: Do
order: 7
---

# STAGE-TIDY-7

7. The gate is your test run (what every stage is told): a single test while you move
   things, then the tidy gate, never the whole suite before it. Write nothing about the gate into
   your file: its report is the record.
