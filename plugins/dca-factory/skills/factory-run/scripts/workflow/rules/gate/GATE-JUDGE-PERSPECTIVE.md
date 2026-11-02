---
id: GATE-JUDGE-PERSPECTIVE
title: Every confirmed finding names a review perspective
part: check
reports:
- judge-perspective
note: a confirmed finding names a perspective the profile does not know — experimental, said and not refused
---

# GATE-JUDGE-PERSPECTIVE

**When:** the document gate runs, over the confirmed findings of the judge's verdict

**Why:** the findings are counted per perspective; a name the profile does not know — `plan`, `—`, `clean-code /
ddd` — frays the figures, and a rate per perspective says nothing. Experimental: the gate says it and lets the story
pass, until the judges keep to it; the figures count such a finding as `other` meanwhile.
