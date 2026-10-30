---
id: RUN-ROUTE-6
part: decision
fail: it names no record (exit 1)
goes.fail: stop
ask: the story waits for the record it names (exit 3)
goes.ask: stop
---

# RUN-ROUTE-6

**When:** a stage's file ends in `## needs-human`

**Why:** a stage that cannot decide stops and asks
