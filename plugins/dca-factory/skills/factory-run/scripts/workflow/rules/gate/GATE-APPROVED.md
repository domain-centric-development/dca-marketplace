---
id: GATE-APPROVED
part: check
reports:
- approved
pass: `approved`, `adopted` or `delivered`
fail: any other status, `draft` included
skip: no `status:` — the project releases otherwise
---

# GATE-APPROVED

**When:** every gate, where the story carries `status:`

**Why:** a human releases a story before code is written
