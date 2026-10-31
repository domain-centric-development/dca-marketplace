---
id: STAGE-JUDGE-1
part: told
stages:
- judge
section: Do
marked: stage-judge/SKILL.md
order: 1
---

# STAGE-JUDGE-1

The change is reviewed from **ddd**, **hexagonal** and **clean-code**, one pass each, kept apart in the
report. These three are part of the method, not project configuration: they always run and no
profile switches them off. The passes are not yours where a review file exists: the pipeline starts
one reviewer per perspective before you, each applying its skill in its own context, and you
**converge** — read `reviews/<perspective>.md`, confirm every must-fix and should-fix in the code at the
file and line it names (or drop it, with the reason), deduplicate across the files, and judge. A
reviewer that did not build and a judge that did not review is the point of the split; a judge who
reviews again in its own context puts the bias back that the files took out. Only a perspective
**without** a file is yours to run — load its carrier and say so. There is no fourth built-in: the method's own audit skill, where a
project has one, is an *added* perspective the profile names — worth it for an adoption, where the
question is how the existing code stands against the method, and not for a story that the rule
suite already holds to it.
