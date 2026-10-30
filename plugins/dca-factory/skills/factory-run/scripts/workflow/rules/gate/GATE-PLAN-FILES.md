---
id: GATE-PLAN-FILES
part: check
reports:
- plan-files
pass: every file planned `new` is there, every one planned `removed` is gone
fail: a planned file is missing or still there — write it, `git rm` it, or plan again
skip: the plan has no `## Files`
---

# GATE-PLAN-FILES

**When:** the build gate (contract 22 on)

**Why:** the plan's files are a promise; an explanation is none
