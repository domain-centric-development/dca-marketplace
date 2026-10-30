---
id: GATE-ENVIRONMENT
part: decision
reports:
- environment
fail: the shell running the gate lacks a tool — put it on the PATH
goes.fail: stop
---

# GATE-ENVIRONMENT

**When:** every gate that runs a command

**Why:** a tool missing from the gate's PATH is no stage's fault — no round is spent on it
