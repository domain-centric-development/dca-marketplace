---
id: RUN-INTEGRATE-1
title: A story reaches the main line through the integrate gate
part: decision
stages:
- integrate
pass: the target is merged into the story's branch and the integrate gate runs
fail: the main line refuses — a round is spent and the build stage runs again with the gate's report; a conflict goes to the integrate stage first, which resolves it
goes.fail:
- integrate
- build
---

# RUN-INTEGRATE-1

**When:** a story's stages passed in its worktree

**Why:** a story reaches the main line only through the integrate gate
