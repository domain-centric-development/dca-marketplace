---
id: GATE-PASS-PLAN
title: The plan gate records what later gates compare against
part: pass
reports:
- story
pass: the story's digest, the baseline of the tests that existed before it (once per story, in git) and the plan's signal are recorded
note: the story is already delivered — it is checked and its marks are left as they are
---

# GATE-PASS-PLAN

**When:** the plan gate has passed for a story that is not yet delivered

**Why:** what the later gates compare against is taken once, when the plan holds
