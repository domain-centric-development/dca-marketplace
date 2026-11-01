---
id: GATE-TASK
title: A task has no criteria and closes only open findings
part: check
kinds:
- task
reports:
- task
pass: the task has no criteria, and every finding it closes is open
fail: the task has a criterion, or it `closes:` a finding that is not open
---

# GATE-TASK

**When:** the plan gate of a task runs

**Why:** a task changes no behaviour; the existing suite is its evidence
