---
id: GATE-APPROVED
title: A story is released before code is written
part: check
reports:
- approved
pass: the story's status is `approved`, `adopted` or `delivered`
fail: the story has any other status, `draft` included
skip: the story has no `status:` — the project releases otherwise
---

# GATE-APPROVED

**When:** a gate runs for a story that carries `status:`

**Why:** a human releases a story before code is written
