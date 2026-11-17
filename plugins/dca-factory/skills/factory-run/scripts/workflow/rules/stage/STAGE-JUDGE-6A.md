---
id: STAGE-JUDGE-6A
part: told
why: a review kept finding old code and new instances of one defect round after round, and the story never converged
stages:
- judge
section: Do
order: 10
---

# STAGE-JUDGE-6A

6a. **Name the class, find every instance, judge what the round changed.** Each defect row names, from the lists,
   what has to change (`Target`: story, plan, code, test, docs, glossary, profile), the kind of correction (`Type`:
   assignment, checking, algorithm, interface, relationship, timing, documentation, duplication, naming, dead-code,
   comment, traceability — test, scenario and criterion not leading to one another —, domain-concept, domain-boundary,
   domain-invariant, domain-term) and `Qualifier` (missing, incorrect,
   extraneous) — the lessons count them (`GATE-JUDGE-CLASS`); `Defect` still opens with the class in a word or two
   (`unchecked null`, `refusal not translated`). Before the verdict, search the story's footprint for every further
   instance — all go into this round, never one per round. A defect on code the story did not write is a row
   like any other (the pipeline reads its origin from the diff; it costs no round). From round two, review what the round
   changed — `story.diff` against `.judge-previous.md`: a new blocking finding belongs on a line the round changed or a
   place the previous verdict named; one elsewhere is recorded as a minor.
