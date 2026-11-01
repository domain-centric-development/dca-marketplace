---
id: GATE-SPEC-TESTS
title: Every criterion that holds keeps the test the spec names
part: check
reports:
- spec-tests
pass: every test the spec names for what the story changes is there
fail: a test the spec names is gone — it goes under tests.md's `## Moved tests` as it is now
---

# GATE-SPEC-TESTS

**When:** the document, adopt or integrate gate runs, where the story changes a spec

**Why:** every criterion that holds keeps the test the spec names
