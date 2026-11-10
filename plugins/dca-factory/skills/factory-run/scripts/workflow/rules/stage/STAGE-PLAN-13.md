---
id: STAGE-PLAN-13
part: told
why: a stage could make its own gate green by changing what judges it, such as the profile or the rule selection
stages:
- plan
section: Do
order: 24
---

# STAGE-PLAN-13

13. **Announce a change to what judges the story.** The stack profile and the paths of its `guarded:` key —
   the commit hook, the architecture suite's rule selection and test classes — decide whether a gate is green.
   No stage changes them unless the plan lists the path under `## Guarded changes` with a one-line reason: the
   gate lets exactly those pass, the runner lets the stages edit exactly those, and the acceptance shows their
   diff first. A scaffold entry a guarded file asks to remove once the code it waits for exists (a rule on
   `warn` until the first module) is such a change — announce its removal. Switching a rule off or adding an
   exception to make a gate green is not a reason: that is a question for a person (`## needs-human`).
