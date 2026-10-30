---
id: GATE-DOCUMENTED
part: check
reports:
- documented
pass: every path resolves and every line names its source
fail: a path that does not resolve, a line without `Verified by`, or a `## needs-human`
---

# GATE-DOCUMENTED

**When:** the document gate

**Why:** a document claim is checkable against the code
