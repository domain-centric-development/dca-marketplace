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

13. A change to the profile or a `guarded:` path (hook, rule selection, architecture tests) only when listed under
   `## Guarded changes` with a one-line reason (`GATE-GUARDED`) — also removing a scaffold entry once its code exists;
   switching a rule off or adding an exception to turn a gate green is `## needs-human`, never a reason.
