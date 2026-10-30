---
id: GATE-CONTRACT
part: check
reports:
- contract
pass: the profile's `contract:` is the gate's
fail: `contract:` is no number, or newer than the gate — `factory.sh update` first
note: no `contract:`, or an older one — read as it is
---

# GATE-CONTRACT

**When:** every gate

**Why:** a gate older than the profile would ignore what it does not know
