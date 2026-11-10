---
id: STAGE-JUDGE-6
part: told
why: a criterion counted as met on a green test whose assertion could never fail
stages:
- judge
section: Do
order: 10
---

# STAGE-JUDGE-6

6. Check the story once more against the criteria: is each one actually met by behaviour, not just
   by a green test? A test that asserts too little is a **test** defect and belongs in the report. Before a
   criterion counts as met, ask of its test's assertion: **could it fail?** With the behaviour absent — the
   button still there, the message still shown — would it turn red? An assertion on a mechanism the code does
   not use, a count of something never written, an absence that held before the story is green whatever the
   code does: a test defect (`back: test`), not a proof.
   An adapter test whose stub throws a failure the criterion's port test does not assert — another type, a
   parent, no port test at all — proves the page for a refusal the use case may never raise: a test defect
   (`back: test`). Where the plan's `## Context` says the context returns its refusals, the stub returns a
   case of the port's result and the type holds that seam; a stub there that throws a refusal instead of
   returning its case is the defect, and so is a helper that runs a use case to arrange a state and
   ignores its result.
