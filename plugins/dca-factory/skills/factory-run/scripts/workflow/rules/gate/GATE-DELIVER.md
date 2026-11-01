---
id: GATE-DELIVER
title: A story is delivered by the gate that last checked it
part: pass
reports:
- integrate
- spec
- delivered
- findings
- story
pass: the story is in its worktree and is delivered once integrated (the runner's integrate step), or it is in the checkout and the delivery is written — the spec merged, `status: delivered`, the judge's confirmed findings kept
fail: the spec after the story would not hold its shape — nothing is written
note: the story is already delivered — it is checked and its marks are left as they are
---

# GATE-DELIVER

**When:** the document or adopt gate has passed and nothing failed

**Why:** a story is delivered by the gate that last checked it, never by a stage
