---
id: STAGE-BUILD-5
part: told
why: a stage ran the whole suite before the gate ran the same commands, paying twice for one answer
stages:
- build
section: Do
order: 7
---

# STAGE-BUILD-5

5. The gate is your test run (what every stage is told): the single test you are
   making green as often as you like, then the build gate, never the whole suite before it. Do not
   finish while the gate names something red — and write nothing about the gate into your file: its
   report is the record.
