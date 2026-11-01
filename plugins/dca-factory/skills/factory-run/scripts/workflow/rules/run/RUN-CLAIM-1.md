---
id: RUN-CLAIM-1
title: Two factories never build the same story
part: decision
pass: the story is claimed, or is ours already — the story runs
fail: there is an id collision or a refused push — a person looks
skip: another factory holds the story — it is skipped
---

# RUN-CLAIM-1

**When:** `claim_remote:` is set and a story is about to run

**Why:** two factories never build the same story
