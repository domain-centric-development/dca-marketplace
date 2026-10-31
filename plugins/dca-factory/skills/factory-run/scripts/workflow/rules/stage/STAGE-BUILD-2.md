---
id: STAGE-BUILD-2
part: told
stages:
- build
section: Do
marked: stage-build/SKILL.md
order: 3
---

# STAGE-BUILD-2

2. Follow the plan's change list. An element the plan did not name is a sign the plan was wrong:
   note it in the build file rather than quietly extending the design. The same holds for a **guard in a
   domain type** — a null check, a trim, a range, a uniqueness rule — that the plan's `## Invariants`
   does not name: it is code no test asked for, so it stays out; name it in the build file as an
   unplanned invariant (`<Element>: <rule>`), and the judge reads it as the plan's gap it is. Every guard
   the plan names has a unit test already — make it pass, add none beside it.
   A file the plan's `## Files` says `removed` goes with `git rm <path>` — on the shell you have — and one it
   says `new` is written; the build gate refuses either left undone (`plan-files`), whatever the build file
   explains. Where a removal or a new file turns out wrong, that is the plan's error: say so under
   `## needs-human` rather than leaving the plan's line unmet.
