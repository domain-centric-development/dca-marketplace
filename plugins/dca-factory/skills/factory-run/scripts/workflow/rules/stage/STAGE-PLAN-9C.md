---
id: STAGE-PLAN-9C
part: told
stages:
- plan
section: Do
order: 14
---

# STAGE-PLAN-9C

9c. **Search what lies outside the story's own files**, and list each hit under `## Files` (`changes:` with what
   follows), so the tidy stage's footprint covers it:
   - a rule whose statement changes → its old wording in doc comments, messages and the other documents;
   - a call the story removes → the target's remaining callers; where none is left, the target and the tests that
     only keep it alive, `changes: removed`;
   - a check, a literal or a mapping the story adds → the same one elsewhere: a second copy is named, a third is
     lifted into one place.
   Nothing found is no line. A search the plan skipped is a finding the judge ranks against the plan.
