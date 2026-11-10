---
id: GATE-GUARDED
title: A plan announces the guarded paths it will change, each with a reason
part: check
reports:
- guarded
pass: every path under `## Guarded changes` is guarded and carries a reason
fail: a path there is not guarded, or carries no reason — the plan names it again
---

# GATE-GUARDED

**When:** the plan gate runs and the plan has a `## Guarded changes` section

**Why:** a story that changes what judges it — the stack profile, the rule selection, the commit hook — does so in the open: the plan says which file and why, the gate lets exactly those pass, and the acceptance shows their diff first
