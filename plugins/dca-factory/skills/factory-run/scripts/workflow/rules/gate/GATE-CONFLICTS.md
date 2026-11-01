---
id: GATE-CONFLICTS
title: A merge is finished before it is checked
part: check
reports:
- conflicts
pass: there is no unmerged path and no conflict marker
fail: there is an unmerged path, or a conflict marker in a file the story changed
---

# GATE-CONFLICTS

**When:** the integrate gate runs

**Why:** a merge is finished before it is checked
