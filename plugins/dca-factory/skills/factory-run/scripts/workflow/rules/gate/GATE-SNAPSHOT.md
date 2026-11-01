---
id: GATE-SNAPSHOT
title: A commit is checked as it will be committed
part: decision
stages:
- commit
reports:
- snapshot
pass: the index is the tree checked
fail: the working tree differs from the index (stash the rest), or the index changed during the run
note: the commit holds the backlog alone — there is no snapshot and no check unless `checks.backlog` names some — or the working tree is checked as it is, without `--staged`
---

# GATE-SNAPSHOT

**When:** the commit hook runs (`--staged`)

**Why:** a commit is checked as it will be committed
