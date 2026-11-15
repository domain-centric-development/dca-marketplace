---
id: GATE-MINOR-QUESTION
title: A round asks no person about a minor
part: check
stages:
- test
- build
- tidy
reports:
- minor-question
pass: no open question of the round cites only what the judge ranked minor
fail: an open question a stage asked in a round cites only places the judge ranked minor
---

# GATE-MINOR-QUESTION

**When:** a gate of the test, build or tidy stage runs while the judge's last verdict sent the story back (contract 36 on)

**Why:** a minor blocks nothing; a round repairs what sent the story back, and a minor stays in the findings, shown at
the acceptance

The places compared are `<file>:<line>` by file name and line: those the question's record cites, and those of the
judge's `## Confirmed defects` table with their severity. A question that cites a blocker or a major, or no place at
all, is not this check's — a person still decides what blocks.
