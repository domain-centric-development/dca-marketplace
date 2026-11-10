---
id: STAGE-PLAN-7
part: told
why: a detail the story specified but no criterion carried was covered by no test and built by no stage
stages:
- plan
section: Do
order: 7
---

# STAGE-PLAN-7

7. List the acceptance criteria by **key** — the story's keys verbatim, the later stages and the
   gate join on them — and give each its level (step 8). The criterion's text stays in the story;
   a plan that retypes it says nothing the reader does not have. The pipeline writes these lines:
   `factory-cli.py --plan-skeleton <story>` (the runner runs it; in a session run it yourself
   before the stage) puts the file's headings and one line per key in place. A story written in
   scenarios keeps its rules and each scenario's steps;
   plan within `## Out of scope` — what it lists is not planned, however close it lies. Add a criterion for every concrete detail the story specifies (wording,
   placement, ordering): a detail that is not a criterion is a detail no test will cover and no
   stage will build. A clause about a state that did not come about — not saved, not sent, unchanged —
   says how a person sees it (the list as it was, the old value still on the page, no new entry): write
   it after the criterion's level where the story leaves it implicit, and where neither the story nor
   the product description says it, choose the plainest sign and record it under `## Open assumptions`
   — the run goes on and the judge sees the assumption. An example of a rule sits where the rule
   differs from the obvious neighbour — a rounding exactly on the half cent, where rounding half up and
   half to even part; a limit on both sides of it. Where the story's example is one both rules answer
   alike, the rule's line under `## Invariants` names the value that tells them apart, so its unit test
   uses it.
