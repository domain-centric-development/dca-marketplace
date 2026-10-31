---
id: STAGE-BUILD-8
part: told
stages:
- build
section: Do
marked: stage-build/SKILL.md
order: 10
---

# STAGE-BUILD-8

8. **A task** (`kind: task`) has no test written for it: the existing suite is the measure, and the build gate runs
   every test command whole. Change what the plan names and nothing an actor sees; change no test that existed
   before (the gate refuses it), add one where it pins down what the change keeps. A test that goes red is a
   behaviour you changed — put it back, or say under `## Deviations from the plan` that the task is a story.
