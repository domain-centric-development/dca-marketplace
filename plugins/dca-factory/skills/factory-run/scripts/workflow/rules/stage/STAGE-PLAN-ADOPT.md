---
id: STAGE-PLAN-ADOPT
part: told
stages:
- plan
kinds:
- adopt
section: Adopt mode
marked: stage-plan/SKILL.md
---

# STAGE-PLAN-ADOPT

A story with `status: adopted` describes behaviour the project already has; nothing is built. The plan
restates its scenarios with their keys and, for each, names **where the behaviour lives** (file and line)
and **which existing test covers it** (file, class, method) — or that none does. It plans no change to
production code and no change to an existing test. A scenario the code does not show at all is not
adoptable: stop with a `## needs-human` — the story describes behaviour the system does not have.
Step 8a applies to what the scenarios exercise instead of what changes: under `## Invariants`, one line per
aggregate, entity, value object and domain service the adopted behaviour runs through, with the rules it
enforces today, its guards included (`- <Element>: <rule>; <rule>`, or `- <Element>: none — <why>`); where the
scenarios exercise no domain type, one line `- none — <why>`. The test gate refuses an adoption without a line.
