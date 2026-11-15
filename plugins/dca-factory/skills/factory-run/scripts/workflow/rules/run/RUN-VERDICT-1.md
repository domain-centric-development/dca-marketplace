---
id: RUN-VERDICT-1
title: The judge decides whether a story goes on
part: decision
stages:
- judge
pass: the judge writes `verdict: pass` — on to document
goes.pass: document
fail: changes requested — the verdict is `changes-requested`, a round, back to `back:` (test) or build; or it is `story-conflict`, missing or another one, and the story stops (exit 1)
goes.fail:
- build
- test
- stop
---

# RUN-VERDICT-1

**When:** the judge wrote its verdict

**Why:** the judge decides whether the story goes on, not how it is fixed

The verdict is weighed by its rows before it decides: a `changes-requested` whose blocking rows all lie on code the
story did not write — their origin read from the story's diff — or, from the second round on, on lines the round did
not touch and no earlier verdict named, goes on as a pass; the rows are kept in the story's findings and cost no round.
A verdict that sends the story back keeps the diff it was given on (`.judge-previous.diff`) for the next round.
