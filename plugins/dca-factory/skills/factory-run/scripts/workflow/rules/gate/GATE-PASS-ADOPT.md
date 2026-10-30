---
id: GATE-PASS-ADOPT
part: pass
reports:
- plan-adopts
pass: whole: the story becomes `status: adopted` and runs the adopt path; split: the held scenarios move to a story `<id>-holds` with `status: adopted`, this one builds the rest
---

# GATE-PASS-ADOPT

**When:** the plan gate passed and the plan's `## Adopt` holds

**Why:** what already holds is adopted, not built again
