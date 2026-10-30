---
id: RUN-VERDICT-1
part: decision
stages:
- judge
pass: `verdict: pass` — on to document
goes.pass: document
fail: `changes-requested`: a round, back to `back:` (test) or build; `story-conflict`, a missing or another verdict: the story stops (exit 1)
goes.fail:
- build
- test
- stop
---

# RUN-VERDICT-1

**When:** the judge wrote its verdict

**Why:** the judge decides whether the story goes on, not how it is fixed
