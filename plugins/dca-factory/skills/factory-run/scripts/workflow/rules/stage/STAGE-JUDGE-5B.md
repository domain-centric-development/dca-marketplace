---
id: STAGE-JUDGE-5B
part: told
stages:
- judge
section: Do
order: 9
---

# STAGE-JUDGE-5B

5b. A **planned change left undone** — a file the plan's `## Files` removes still there, a change it lists not
   made, a step the build file says it could not take — is a confirmed `major` against the plan (`plan`
   perspective): `changes-requested`. Where the build could not take the step for a real reason and the story is
   not met without it, the plan was wrong, and that is a `story-conflict` — not a pass. The build gate refuses a `new` or `removed` line that
   did not happen (`plan-files`); the rest is yours.
   One case is a `minor` instead: the build **left out an addition on purpose** — a type, a field, a layer — names
   it under `## Deviations from the plan` with its reason, and the reason holds in the code: every criterion is
   met without it, no invariant of the plan is lost, nothing the plan removes is left, and the project's
   conventions do not ask for it. Then the plan was wrong and the code is right — record it as a `minor` (`plan`
   perspective) that names the planned element and the reason, so the deviation is on record, not silent. It
   does not change the verdict.
