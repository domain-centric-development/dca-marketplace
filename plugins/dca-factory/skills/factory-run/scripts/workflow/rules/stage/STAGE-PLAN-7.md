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

7. List criteria by **key**, verbatim — later stages and the gate join on them — each with its level (step 8); the
   text stays in the story. `factory-cli.py --plan-skeleton <story>` writes headings and one line per key (the runner
   runs it; by hand, run it first). A story in scenarios keeps its rules and each scenario's steps.
   - `## Out of scope` is not planned, however close.
   - Every concrete detail the story specifies (wording, placement, ordering) gets a criterion — else no test covers
     it and no stage builds it.
   - A clause about something that did not happen (not saved, not sent, unchanged) says how a person sees it (the list
     as it was, the old value on the page, no new entry). Implicit → write it after the level; neither story nor
     product says → choose the plainest sign, record it under `## Open assumptions`.
   - An example sits where the rule differs from its obvious neighbour (exactly the half cent, where half-up and
     half-even part; both sides of a limit). Where the story's example is one both rules answer alike, the
     `## Invariants` line names the value that tells them apart, so its unit test uses it.
