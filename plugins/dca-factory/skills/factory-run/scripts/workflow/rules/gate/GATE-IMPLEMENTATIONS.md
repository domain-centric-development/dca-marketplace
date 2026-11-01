---
id: GATE-IMPLEMENTATIONS
title: Implementations of one spec prove the same scenarios
part: decision
stages:
- commit
reports:
- implementations
- contract
pass: every implementation reports every scenario the config names, green
fail: an implementation lacks a scenario or reports it red
---

# GATE-IMPLEMENTATIONS

**When:** `factory.sh check --parity <config>` runs over several implementations' reports

**Why:** two implementations of the same spec prove the same scenarios
