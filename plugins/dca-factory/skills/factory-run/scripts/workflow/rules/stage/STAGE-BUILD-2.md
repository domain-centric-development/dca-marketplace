---
id: STAGE-BUILD-2
part: told
why: the build added guards and elements the plan never named, code no test asked for and no plan accounted for
stages:
- build
section: Do
order: 3
---

# STAGE-BUILD-2

2. Follow the plan's change list. An unnamed element means the plan was wrong: note it in build.md, do not extend the
   design quietly.
   - A **domain guard** (null check, trim, range, uniqueness) not under the plan's `## Invariants` is code no test asked
     for: leave it out, name it in build.md as an unplanned invariant (`<Element>: <rule>`) — the judge reads it as the
     plan's gap. Planned guards have unit tests already: make them pass, add none.
   - The incoming adapter does not check such a rule again: a missing field is passed on as missing (no default turning
     absence into empty, no annotation repeating the value object's refusal) — the value object's refusal answers.
   - `## Files` says `removed` → `git rm <path>`; `new` → write it. Either left undone is refused (`plan-files`), whatever
     build.md explains. A wrong removal or new file is the plan's error → `## needs-human`.
