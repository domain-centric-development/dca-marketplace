---
id: GATE-SNAPSHOT
part: decision
stages:
- commit
reports:
- snapshot
pass: the index is the tree checked
fail: the working tree differs from the index — stash the rest, or the index changed during the run
note: the backlog alone — no snapshot, no check unless `checks.backlog` names some; or the working tree as it is, without `--staged`
---

# GATE-SNAPSHOT

**When:** the commit hook (`--staged`)

**Why:** a commit is checked as it will be committed
