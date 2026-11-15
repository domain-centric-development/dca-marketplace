---
id: STAGE-JUDGE-TASK
part: told
why: a change declared invisible could alter behaviour and pass without the red test a story needs
stages:
- judge
kinds:
- task
section: Task mode
order: 12
---

# STAGE-JUDGE-TASK

`kind: task` claims nothing an actor sees changed. Check first: does the diff change an answer, a page, a stored value,
a published event, a refusal? Then it is a story — `story-conflict`, naming the behaviour. Otherwise judge as usual
(perspectives, the plan's `## Files`) and check every finding row `closes:` names is settled by the diff (file, line);
one unsettled → `major`. `## Criteria re-checked`: `- none: a task`.
