---
id: STAGE-PLAN-8A
part: told
why: domain types gained guards no plan named and no unit test covered
stages:
- plan
section: Do
order: 9
---

# STAGE-PLAN-8A

8a. **Name the invariants of every domain type you change** — each aggregate, entity, value object and domain service
   in `## Changes`: the rules it must never break (from the criteria, and its guards: required, trimmed, in range,
   unique in its aggregate). One line each under `## Invariants`, rules separated by `;`; one rule = one thing the type
   refuses or keeps = one unit test. No rules → `none — <why>`.
   - A value object built from input (a field a request, form or message fills) names refusing a missing value as a
     rule, with its failure (a missing title refused like an empty one). A value only code passes needs none.
   - The build writes no guard not named here: an unplanned check is code no test asked for.
   - Name also the types the build will only reach (a new way to make an identifier from a request among them): the
     test gate refuses a changed domain type without its line, the build gate one the change touched that the plan
     never named (`invariants-cover`). One the build reaches after all gets its line in build.md, never a plan change
     once tests are written.
