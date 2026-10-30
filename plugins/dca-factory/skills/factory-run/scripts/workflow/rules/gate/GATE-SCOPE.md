---
id: GATE-SCOPE
part: decision
stages:
- commit
reports:
- scope
- test
- compile
- architecture
- format
pass: every command in scope ran green
fail: a required command missing or red
skip: out of scope (a required one: CI has to run it), or not declared
note: red, but not required — it does not decide
---

# GATE-SCOPE

**When:** the commit hook and CI, for each check

**Why:** a check outside the scope is named, not hidden
