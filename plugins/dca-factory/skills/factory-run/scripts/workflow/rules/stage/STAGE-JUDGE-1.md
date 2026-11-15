---
id: STAGE-JUDGE-1
part: told
why: a judge that reviewed again in its own context put back the bias the separate reviews took out
stages:
- judge
section: Do
order: 1
---

# STAGE-JUDGE-1

Reviewed from **ddd**, **hexagonal** and **clean-code**, one pass each, kept apart. They are the method's: always run,
no profile switches them off. Where a review file exists the pass is not yours — the reviewers ran before you, each in
its own context. You **converge**: read `reviews/<perspective>.md`, confirm each must-fix and should-fix in the code at
its file and line (or drop it, with the reason), deduplicate across files, judge. Never review again in your own context
— that puts back the bias the split removed. Only a perspective **without** a file is yours: load its carrier, say so. No
fourth built-in: the method's audit skill is an *added* perspective — worth it for an adoption, not for a story the rule
suite already holds.
