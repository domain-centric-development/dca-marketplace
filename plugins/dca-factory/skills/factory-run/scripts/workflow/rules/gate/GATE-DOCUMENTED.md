---
id: GATE-DOCUMENTED
title: Every document claim is checkable against the code
part: check
reports:
- documented
pass: every path resolves and every line names its source
fail: a path does not resolve, a line has no `Verified by`, or there is a `## needs-human`
---

# GATE-DOCUMENTED

**When:** the document gate runs

**Why:** a document claim is checkable against the code
