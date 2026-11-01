---
id: RUN-OWNED-1
title: A run stops when what a person owns changed
part: decision
pass: nothing the person owns changed
fail: what the person owns changed — the run stops (exit 7) and the story waits until `--owned-confirm`
goes.fail: stop
---

# RUN-OWNED-1

**When:** a stage window ends

**Why:** the story and the answers are the person's
