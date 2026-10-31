---
id: STAGE-JUDGE-5B
part: told
stages:
- judge
section: Do
marked: stage-judge/SKILL.md
order: 9
---

# STAGE-JUDGE-5B

5b. A **planned change left undone** — a file the plan's `## Files` removes still there, a change it lists not
   made, a step the build file says it could not take — is a confirmed `major` against the plan (`plan`
   perspective), never a `minor`: `changes-requested`, whatever reason the build file gives. Where the reason is
   real, the plan was wrong, and that is a `story-conflict` — not a pass. The build gate refuses a `new` or
   `removed` line that did not happen (`plan-files`); the rest is yours.
