---
id: GATE-PROFILE
title: Every profile key is one the pipeline reads
part: check
reports:
- profile
note: a profile key is unknown to the pipeline — the key is ignored and the nearest known one is named
---

# GATE-PROFILE

**When:** a gate runs, for each key of the stack profile

**Why:** a key the pipeline does not read is a typo nobody would notice
