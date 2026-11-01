---
id: GATE-SCOPE
title: A check outside the scope is named, not hidden
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
fail: a required command is missing or red
skip: a command is out of scope (a required one: CI has to run it) or not declared, or the commit holds the installed pipeline alone (`.agents/factory/`, its commit hook, the skill copies) — it runs none, the pipeline is verified where it is built
note: a command is red but not required — it does not decide
---

# GATE-SCOPE

**When:** the commit hook and CI run, for each check

**Why:** a check outside the scope is named, not hidden
