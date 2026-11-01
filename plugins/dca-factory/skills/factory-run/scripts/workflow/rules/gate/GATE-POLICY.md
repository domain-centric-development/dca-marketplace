---
id: GATE-POLICY
title: The required commands are known commands
part: decision
stages:
- commit
reports:
- policy
pass: `required:` names known commands only
fail: `required:` names another key
note: there is no `required:` — nothing is mandatory, a red command still fails
---

# GATE-POLICY

**When:** the commit hook and CI (`factory.sh check`) run

**Why:** `required:` says which commands must hold; a key nothing runs is a promise nobody keeps
