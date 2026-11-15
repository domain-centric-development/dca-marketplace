---
id: STAGE-BUILD-8
part: told
why: a change meant to alter nothing visible has no test of its own, so a changed older test would hide a changed behaviour
stages:
- build
section: Do
order: 10
---

# STAGE-BUILD-8

8. **Task** (`kind: task`): no new criterion test — the existing suite, run whole by the build gate, is the measure.
   Change what the plan names and nothing an actor sees; no earlier test changed (refused); add one where it pins what the
   change keeps. A red test = behaviour you changed: put it back, or say under `## Deviations from the plan` that the task
   is a story.
