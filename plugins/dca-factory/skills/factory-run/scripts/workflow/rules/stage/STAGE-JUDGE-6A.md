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

6a. **Name the class, find every instance, judge what the round changed.** A defect row names its class in a word
   or two in `Defect` (`unchecked null`, `refusal not translated`), and before you write the verdict you search the
   story's footprint for every further instance of that class — all of them go into this round, never one per
   round. A defect on code the story did not write is recorded like any other row: the pipeline reads its origin
   from the story's diff, keeps it in the story's findings and lets it cost no round. From the second round on,
   review what the round changed — `story.diff` against the previous verdict (`.judge-previous.md`): a new blocking
   finding belongs on a line the round changed or a place the previous verdict named; one elsewhere the pipeline
   records as a minor.
