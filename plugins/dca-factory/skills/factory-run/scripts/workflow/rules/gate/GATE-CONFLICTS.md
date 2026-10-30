---
id: GATE-CONFLICTS
part: check
reports:
- conflicts
pass: no unmerged path, no conflict marker
fail: an unmerged path, or a marker in a file the story changed
---

# GATE-CONFLICTS

**When:** the integrate gate

**Why:** a merge is finished before it is checked
