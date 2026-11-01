---
id: GATE-PASS-ADOPT
title: A story whose scenarios already hold is adopted
part: pass
reports:
- plan-adopts
pass: the plan adopts the whole story — it becomes `status: adopted` and runs the adopt path — or splits it — the held scenarios move to a story `<id>-holds` with `status: adopted` and this one builds the rest
---

# GATE-PASS-ADOPT

**When:** the plan gate passed and the plan's `## Adopt` holds

**Why:** what already holds is adopted, not built again
