---
id: STAGE-PLAN-9C
part: told
why: old wordings, remaining callers and second copies outside the story's files were left behind for the judge to find
stages:
- plan
section: Do
order: 14
---

# STAGE-PLAN-9C

9c. **Search outside the story's own files**; list each hit under `## Files` (`changes:` with what follows), so tidy's
   footprint covers it:
   - a rule whose statement changes → its old wording in doc comments, messages, other documents;
   - a call removed → the target's remaining callers; none left → the target and tests that only keep it alive,
     `changes: removed`;
   - a check, literal or mapping added → the same one elsewhere: a second copy is named, a third lifted into one place.
   Nothing found → no line. A skipped search is a finding the judge ranks against the plan.
