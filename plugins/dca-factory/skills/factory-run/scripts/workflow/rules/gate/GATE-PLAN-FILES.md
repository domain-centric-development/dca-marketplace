---
id: GATE-PLAN-FILES
title: The files a plan names are there or gone
part: check
reports:
- plan-files
pass: every file planned `new` is there and every one planned `removed` is gone
fail: a planned file is missing or still there — it has to be written, removed with `git rm`, or planned again
skip: the plan has no `## Files`
---

# GATE-PLAN-FILES

**When:** the build gate runs (contract 22 on)

**Why:** the plan's files are a promise; an explanation is none
