---
id: GATE-TESTS-KEPT
title: A test that held before the story keeps holding
part: check
reports:
- tests-kept
pass: every earlier test is kept (lines added only), or each change is backed by the plan and an answer
fail: an earlier test is changed, removed or switched off without backing
skip: there is no baseline (outside git), or a lost one
note: a test is arranged around its assertions, or renamed with what it tests
---

# GATE-TESTS-KEPT

**When:** a listing gate runs, against the tests that existed before the story

**Why:** a test that held before the story keeps holding unless a person backed the change
