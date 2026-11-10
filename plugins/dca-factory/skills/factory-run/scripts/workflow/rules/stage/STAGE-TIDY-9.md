---
id: STAGE-TIDY-9
part: told
why: a tidy step that found the story, the plan and the tests at odds changed a test or the plan instead of asking
stages:
- tidy
section: Do
order: 30
---

# STAGE-TIDY-9

9. **When the specification contradicts itself, stop.** Where the story, the plan and the tests cannot all hold,
   end the stage with `## needs-human`: `decision: <story>-<nn>` and a line `contradiction: <what cannot all hold>`,
   its record beside the story. Never edit a test or the plan to resolve it — the stop is counted apart from a
   failure, and a person decides which side is right.
