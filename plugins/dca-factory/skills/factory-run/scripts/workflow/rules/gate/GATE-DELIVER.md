---
id: GATE-DELIVER
part: pass
reports:
- integrate
- spec
- delivered
- findings
- story
pass: in the story's worktree: delivered once integrated (the runner's integrate step); in the checkout: the delivery is written — the spec merged, `status: delivered`, the judge's confirmed findings kept
fail: the spec after the story would not hold its shape — nothing is written
note: a delivered story is checked and its marks are left as they are
---

# GATE-DELIVER

**When:** the document or adopt gate passed and nothing failed

**Why:** a story is delivered by the gate that last checked it, never by a stage
