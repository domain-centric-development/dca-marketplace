---
id: GATE-INVARIANT-BREAKS
part: check
reports:
- invariant-breaks
pass: each rule test is red before the build, or turns red under its break patch
fail: a rule test stays green under its break, or has no patch that applies
---

# GATE-INVARIANT-BREAKS

**When:** the test gate of a story with rules in `gate:invariants` (contract 25 on)

**Why:** a rule's test that is green already must still notice a break of the rule
