---
id: RUN-ACCEPT-1
part: decision
stages:
- document
wait: the run ends with exit 3; the story keeps its worktree or the checkout
goes.wait: stop
---

# RUN-ACCEPT-1

**When:** the document gate waits for an acceptance

**Why:** a story waiting for its person keeps what it holds
