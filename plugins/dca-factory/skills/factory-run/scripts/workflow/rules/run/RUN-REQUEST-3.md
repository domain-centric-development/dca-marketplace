---
id: RUN-REQUEST-3
part: decision
pass: exit 0 or 3 — done or waiting
fail: any other exit — failed, kept for a retry
note: interrupted (a signal) — queued again
---

# RUN-REQUEST-3

**When:** a request's process ended

**Why:** a request interrupted is not a request failed
