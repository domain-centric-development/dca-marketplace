---
id: RUN-ROUTE-6
title: A stage that cannot decide stops and asks
part: decision
fail: the `## needs-human` names no record — the run exits 1
goes.fail: stop
ask: the `## needs-human` names a record — the story waits for it (exit 3)
goes.ask: stop
---

# RUN-ROUTE-6

**When:** a stage's file ends in `## needs-human`

**Why:** a stage that cannot decide stops and asks
