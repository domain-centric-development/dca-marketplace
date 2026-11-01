---
id: GATE-MOVED
title: A moved target is merged again without a round
part: check
reports:
- moved
fail: the target moved since the merge — it is merged again, no round is spent
goes.fail: integrate
---

# GATE-MOVED

**When:** the integrate gate runs

**Why:** if the main line moved, the step merges again
