---
id: GATE-RED-REPROOF
part: check
reports:
- red-reproof
pass: each moved test is red on the red tree, by its assertion
fail: the red tree does not compile with it, or the test is green there or red by a timeout
---

# GATE-RED-REPROOF

**When:** the tidy gate of a story whose tidy moved a mapped test

**Why:** a refactoring keeps what a test asserts — the moved test is red again on the code before the story
