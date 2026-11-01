---
id: GATE-ENVIRONMENT
title: A tool missing from the PATH costs no round
part: decision
reports:
- environment
fail: the shell running the gate lacks a tool — the tool has to be put on the PATH
goes.fail: stop
---

# GATE-ENVIRONMENT

**When:** a gate that runs a command runs

**Why:** a tool missing from the gate's PATH is no stage's fault — no round is spent on it
