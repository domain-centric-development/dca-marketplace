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

5. Run the single test you are making green as often as you like, then the build gate — never the whole suite first. Do
   not finish while it names something red; write nothing about it into your file.
