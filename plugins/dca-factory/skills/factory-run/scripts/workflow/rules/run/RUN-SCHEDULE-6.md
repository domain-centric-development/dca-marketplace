---
id: RUN-SCHEDULE-6
title: Stories run side by side where they do not meet
part: decision
pass: the runner picks worktrees first, then the order; among peers it picks the one whose context no running story changes
---

# RUN-SCHEDULE-6

**When:** the runner fills its slots (`--parallel`, `FACTORY_PARALLEL`, `parallel:`, else 1)

**Why:** stories run side by side where they do not meet
