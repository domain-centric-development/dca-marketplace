---
id: STAGE-JUDGE-1
part: told
why: a judge that reviewed again in its own context put back the bias the separate reviews took out; a judge that read every review file whole carried their arguments through every later turn
stages:
- judge
section: Do
order: 1
---

# STAGE-JUDGE-1

The change is reviewed from **ddd**, **hexagonal** and **clean-code**, one pass each, kept apart in the
report. These three are part of the method, not project configuration: they always run and no
profile switches them off. The passes are not yours where a review file exists: the pipeline starts
one reviewer per perspective before you, each applying its skill in its own context, and you
**converge** — read the findings, confirm every must-fix and should-fix in the code at the
file and line it names (or drop it, with the reason), deduplicate across the files, and judge. Where the runner
wrote `reviews/findings.md` — one row per finding of the files: perspective, rank, where, what is wrong and the
reviewer's fix — read the rows, and open `reviews/<perspective>.md` only for a finding whose row does not carry
the question or for a file the rows could not read; otherwise read the files. A
reviewer that did not build and a judge that did not review is the point of the split; a judge who
reviews again in its own context puts the bias back that the files took out. Only a perspective
**without** a file is yours to run — load its carrier and say so. There is no fourth built-in: the method's own audit skill, where a
project has one, is an *added* perspective the profile names — worth it for an adoption, where the
question is how the existing code stands against the method, and not for a story that the rule
suite already holds to it.
