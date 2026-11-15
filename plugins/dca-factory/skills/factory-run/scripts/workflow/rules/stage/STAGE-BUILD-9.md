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

9. **Specification contradicts itself → stop.** Story, plan and tests cannot all hold (a criterion asks one thing, a
   test another, the plan a third) → `## needs-human` with `decision: <story>-<nn>` and `contradiction: <the criterion,
   the plan line and the test that cannot all hold>`, record beside the story. Never edit a test or the plan to resolve
   it, never satisfy one side by breaking the other — a person decides which is right.
