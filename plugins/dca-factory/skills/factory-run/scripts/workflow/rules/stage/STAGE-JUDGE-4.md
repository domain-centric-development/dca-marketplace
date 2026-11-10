---
id: STAGE-JUDGE-4
part: told
why: findings the rule suite already enforces were reported again, counting one defect twice
stages:
- judge
section: Do
order: 4
---

# STAGE-JUDGE-4

4. Deduplicate findings that describe the same defect and drop anything the project's own rule
   suite already enforces — a rule catches it every run, a review comment does not.
