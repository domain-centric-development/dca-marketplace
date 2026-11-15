---
id: STAGE-JUDGE-5B
part: told
why: a planned removal or change left undone was ranked minor and the story passed without it
stages:
- judge
section: Do
order: 9
---

# STAGE-JUDGE-5B

5b. A **planned change left undone** (a file `## Files` removes still there, a listed change not made, a step build.md
   could not take) is a confirmed `major` (`plan`): `changes-requested`. Not takeable for a real reason and the story
   unmet without it → the plan was wrong: `story-conflict`, never a pass. The build gate holds `new` / `removed`
   (`plan-files`); the rest is yours.
   Exception, `minor`: the build **left out an addition on purpose** (a type, a field, a layer), named under
   `## Deviations from the plan` with a reason that holds in the code — every criterion met without it, no planned
   invariant lost, nothing the plan removes left, no convention asking for it. Record a `minor` (`plan`) naming the
   element and reason, so the deviation is on record; the verdict does not change.
