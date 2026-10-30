---
id: RUN-ROUTE-3
part: decision
stages:
- plan
pass: the plan gate passes before the stage
fail: the gate refuses — fix it before the stage runs (exit 1)
goes.fail: stop
---

# RUN-ROUTE-3

**When:** the plan stage is next

**Why:** a story that is not ready is refused before anything is spent
