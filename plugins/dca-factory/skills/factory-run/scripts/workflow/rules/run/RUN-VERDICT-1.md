---
id: RUN-VERDICT-1
title: The judge decides whether a story goes on
part: decision
stages:
- judge
pass: the judge writes `verdict: pass` — on to document
goes.pass: document
fail: the verdict is `changes-requested` — a round, back to `back:` (test) or build; or it is `story-conflict`, missing or another one — the story stops (exit 1)
goes.fail:
- build
- test
- stop
---

# RUN-VERDICT-1

**When:** the judge wrote its verdict

**Why:** the judge decides whether the story goes on, not how it is fixed
