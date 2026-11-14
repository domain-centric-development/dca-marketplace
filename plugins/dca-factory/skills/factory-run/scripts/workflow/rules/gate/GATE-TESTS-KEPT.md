---
id: GATE-TESTS-KEPT
title: A test that held before the story keeps holding
part: check
reports:
- tests-kept
pass: every earlier test is kept (lines added only), or each change is backed by the plan and an answer
fail: an earlier test is changed, removed or switched off without backing
skip: there is no baseline (outside git), or a lost one
note: a test is arranged around its assertions, renamed with what it tests, or its locators find the same stable markers on another path
---

# GATE-TESTS-KEPT

**When:** a listing gate runs, against the tests that existed before the story

**Why:** a test that held before the story keeps holding unless a person backed the change

A change counts as arranged, and passes with a note the judge and the acceptance see, where every assertion the test
made is still made: a type the test builds gained a field; a name the story renamed; or a locator that names the
same stable markers as before (`data-test`, `data-testid`) on another path or position, with the expected value and
the assertion method unchanged. A locator that drops or swaps a marker, a changed expected value or matcher, and a
locator without markers stay changes — a plan entry under `## Changed tests` and an answer back them, or nothing does.
