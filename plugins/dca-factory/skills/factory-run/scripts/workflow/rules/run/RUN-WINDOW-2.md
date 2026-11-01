---
id: RUN-WINDOW-2
title: The judge never shares a process with the builder
part: decision
stages:
- judge
- document
pass: one process runs judge and document, and the document gate is re-run
fail: a file is missing, or the gate refuses
goes.fail: again
wait: the document gate waits for the acceptance (exit 3)
goes.wait: stop
---

# RUN-WINDOW-2

**When:** judge and document run shared

**Why:** the judge never shares a process with the builder
