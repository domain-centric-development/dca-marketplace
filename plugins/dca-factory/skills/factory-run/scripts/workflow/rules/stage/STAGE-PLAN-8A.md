---
id: STAGE-PLAN-8A
part: told
stages:
- plan
section: Do
order: 9
---

# STAGE-PLAN-8A

8a. **Name the invariants of every domain type you change.** For each aggregate, entity, value object and
   domain service in `## Changes`: the rules it must never break — what the criteria imply and the guards
   its type implies (a value that is required, trimmed, within a range, unique in its aggregate). One line
   each under `## Invariants`, the rules separated by `;` — each rule gets its own unit test, so one rule
   is one thing the type refuses or keeps; a type without rules of its own says `none — <why>`. A value
   object built from input — a field a request, a form or a message fills — names its refusal of a missing
   value as one of its rules, with the failure its rule names (a missing title refused like an empty one);
   a value only code passes needs no such line. The test stage writes a
   unit test for every rule named here, and the build writes no guard that is not named: a check nobody
   planned is code no test asked for. The test gate refuses a changed domain type without its line.
