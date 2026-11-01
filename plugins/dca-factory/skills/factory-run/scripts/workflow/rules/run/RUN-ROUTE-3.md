---
id: RUN-ROUTE-3
title: The plan gate runs before the plan stage
part: decision
stages:
- plan
pass: the plan gate passes before the stage — the stage runs
fail: the gate refuses — the story has to be fixed before the stage runs (exit 1)
goes.fail: stop
---

# RUN-ROUTE-3

**When:** the plan stage is next

**Why:** a story that is not ready is refused before anything is spent
