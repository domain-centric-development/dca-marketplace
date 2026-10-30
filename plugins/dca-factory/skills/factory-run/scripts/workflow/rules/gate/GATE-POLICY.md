---
id: GATE-POLICY
part: decision
stages:
- commit
reports:
- policy
pass: `required:` names known commands only
fail: it names another key
note: no `required:` — nothing is mandatory, a red command still fails
---

# GATE-POLICY

**When:** the commit hook and CI (`factory.sh check`)

**Why:** `required:` says which commands must hold; a key nothing runs is a promise nobody keeps
