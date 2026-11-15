---
id: STAGE-PLAN-ADOPT
part: told
why: an adoption could claim behaviour the code does not show, or change code where nothing was to be built
stages:
- plan
kinds:
- adopt
section: Adopt mode
order: 19
---

# STAGE-PLAN-ADOPT

`status: adopted`: the behaviour exists; nothing is built. Per scenario, with its key: **where it lives** (file, line)
and **which existing test covers it** (file, class, method) — or none. No production or test change. A scenario the
code does not show → `## needs-human`: not adoptable. Step 8a covers what the scenarios exercise: one `## Invariants`
line per domain type the behaviour runs through, with today's rules and guards (`- <Element>: <rule>; <rule>` or
`- <Element>: none — <why>`); no domain type → `- none — <why>`. The test gate refuses an adoption without a line.
