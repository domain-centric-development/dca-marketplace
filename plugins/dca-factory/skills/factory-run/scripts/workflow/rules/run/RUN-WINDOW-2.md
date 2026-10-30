---
id: RUN-WINDOW-2
part: decision
stages:
- judge
- document
pass: one process for judge and document; the document gate re-run
fail: a file missing, or the gate refusing
goes.fail: again
wait: the document gate waits for the acceptance (exit 3)
goes.wait: stop
---

# RUN-WINDOW-2

**When:** judge and document run shared

**Why:** the judge never shares a process with the builder
