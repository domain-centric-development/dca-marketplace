---
id: GATE-RED-REPROOF
title: A moved test is red again on the red tree
part: check
reports:
- red-reproof
pass: each moved test is red on the red tree, by its assertion
fail: the red tree does not compile with the test, or the test is green there or red by a timeout
---

# GATE-RED-REPROOF

**When:** the tidy gate runs for a story whose tidy moved a mapped test

**Why:** a refactoring keeps what a test asserts — the moved test is red again on the code before the story
