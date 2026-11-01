---
id: GATE-ACCEPTANCE
title: A story waits for a person's acceptance before it counts as delivered
part: pass
reports:
- acceptance
pass: the acceptance record says accepted — the delivery goes on
fail: the acceptance asks for a correction — written into the story, which runs again from plan
goes.fail: plan
wait: no acceptance exists yet — a record `accept-<n>.md` is written beside the story and the story waits (exit 3)
goes.wait: stop
---

# GATE-ACCEPTANCE

**When:** the document gate has passed for a story that is not a task, and the profile's `acceptance:` takes it (`all`, or `pages` with a browser test)

**Why:** a person looks at what a story shows before it counts as delivered
