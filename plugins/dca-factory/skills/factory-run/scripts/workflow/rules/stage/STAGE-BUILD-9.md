---
id: STAGE-BUILD-9
part: told
why: a builder that met a story, a plan and tests that could not all hold edited a test or the plan until the gate went green
stages:
- build
section: Do
order: 30
---

# STAGE-BUILD-9

9. **When the specification contradicts itself, stop.** Where the story, the plan and the tests cannot all hold —
   a criterion asks one thing, a test asserts another, the plan names a third —, end the stage with
   `## needs-human`: `decision: <story>-<nn>` and a line `contradiction: <the criterion, the plan line and the test
   that cannot all hold>`, its record beside the story. Never edit a test or the plan to resolve it, and never make
   the code satisfy one side by breaking the other: the stop is counted apart from a failure, and a person decides
   which side is right.
