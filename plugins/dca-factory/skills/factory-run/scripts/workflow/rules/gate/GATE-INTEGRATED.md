---
id: GATE-INTEGRATED
part: pass
reports:
- published
- checkout
- moved
- integrated
- committed
pass: with `claim_remote:` the story is published as one commit on its claim branch; else the main checkout fast-forwards to the story's commit, the delivery is written and committed (`chore(<context>): deliver <id>`)
fail: the main checkout is on another branch, the target moved (merged again), or the commit failed
---

# GATE-INTEGRATED

**When:** the integrate gate passed in the story's worktree

**Why:** the main line moves only by a fast-forward of a story that held every gate on it
