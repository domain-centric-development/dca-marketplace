---
id: RUN-REQUEST-3
title: An interrupted request is not a failed request
part: decision
pass: the process exits 0 or 3 — the request is done or waiting
fail: the process exits with any other code — the request failed and is kept for a retry
note: the process was interrupted (a signal) — the request is queued again
---

# RUN-REQUEST-3

**When:** a request's process ended

**Why:** a request interrupted is not a request failed
