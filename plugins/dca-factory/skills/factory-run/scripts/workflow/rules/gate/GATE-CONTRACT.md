---
id: GATE-CONTRACT
title: The profile's contract is not newer than the gate's
part: check
reports:
- contract
pass: the profile's `contract:` is the gate's
fail: `contract:` is no number, or is newer than the gate — `factory.sh update` has to run first
note: the profile has no `contract:`, or an older one — it is read as it is
---

# GATE-CONTRACT

**When:** a gate runs

**Why:** a gate older than the profile would ignore what it does not know
