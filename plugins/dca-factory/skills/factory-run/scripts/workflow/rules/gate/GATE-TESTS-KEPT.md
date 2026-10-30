---
id: GATE-TESTS-KEPT
part: check
reports:
- tests-kept
pass: every earlier test kept (lines added only), or each change backed by the plan and an answer
fail: an earlier test changed, removed or switched off without backing
skip: no baseline (outside git), or a lost one
note: a test arranged around its assertions, or renamed with what it tests
---

# GATE-TESTS-KEPT

**When:** the listing gates, against the tests that existed before the story

**Why:** a test that held before the story keeps holding unless a person backed the change
