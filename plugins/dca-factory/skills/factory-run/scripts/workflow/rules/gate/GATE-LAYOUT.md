---
id: GATE-LAYOUT
part: decision
reports:
- layout
fail: the project's layout is one the gate does not read — the hint names the migration
note: with `--project`: the same, as a hint
---

# GATE-LAYOUT

**When:** every gate and the commit hook

**Why:** a profile or a story the gate does not read would leave every check skipped — a green run that covers nothing
