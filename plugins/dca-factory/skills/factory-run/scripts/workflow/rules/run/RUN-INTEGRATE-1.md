---
id: RUN-INTEGRATE-1
part: decision
stages:
- integrate
pass: the target is merged into the story's branch and the integrate gate runs
fail: a conflict — the integrate stage resolves it; a refusal on the main line costs a round
goes.fail:
- integrate
- build
---

# RUN-INTEGRATE-1

**When:** a story's stages passed in its worktree

**Why:** a story reaches the main line only through the integrate gate
