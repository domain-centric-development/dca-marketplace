---
id: RUN-SCHEDULE-6
part: decision
pass: worktrees first, then the order; among peers the one whose context no running story changes
---

# RUN-SCHEDULE-6

**When:** the runner fills its slots (`--parallel`, `FACTORY_PARALLEL`, `parallel:`, else 1)

**Why:** stories run side by side where they do not meet
