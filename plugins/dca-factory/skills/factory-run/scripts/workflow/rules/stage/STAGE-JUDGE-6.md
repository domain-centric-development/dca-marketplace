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

6. Each criterion met by behaviour, not just a green test? A test asserting too little is a **test** defect
   (`back: test`). Before a criterion counts, ask of its assertion: **could it fail** with the behaviour absent (the
   button still there, the message still shown)? Green whatever the code does = a test defect, not a proof:
   - an assertion on a mechanism the code does not use, a count of something never written, an absence that held before
     the story;
   - **arrange result ignored**: a helper that runs a use case to arrange a state and ignores its result;
   - an adapter stub throwing a failure the criterion's port test does not assert (another type, a parent, no port test)
     — it proves the page for a refusal the use case may never raise. Where `## Context` says refusals are returned, the
     stub returns a case of the port's result; a stub throwing there is the defect;
   - **stub read back**: an adapter test that performs an action against a stubbed input port, answers again with the
     state after it and asserts that answer — or whose name claims a change (after completing, after creating, trimmed)
     while its only evidence is what its stub was told. Delete the action and it stays green. A test defect even where a
     port test proves the change: the adapter half shows one state from one arrangement and is named after it.
