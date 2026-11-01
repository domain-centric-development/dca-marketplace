---
id: GATE-LAYOUT
title: The gate reads the project's layout
part: decision
reports:
- layout
fail: the project's layout is one the gate does not read — the hint names the migration
note: it runs with `--project` — the same finding is shown as a hint
---

# GATE-LAYOUT

**When:** a gate or the commit hook runs

**Why:** a profile or a story the gate does not read would leave every check skipped — a green run that covers nothing
