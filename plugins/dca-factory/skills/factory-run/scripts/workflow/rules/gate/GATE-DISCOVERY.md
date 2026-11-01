---
id: GATE-DISCOVERY
title: A discovery report proposes epics and cites real sources
part: decision
stages:
- discover
reports:
- discovery
pass: the report holds
fail: the report's shape or a source it cites does not hold
---

# GATE-DISCOVERY

**When:** `story-gate.py --check-discovery <topic>` runs after a discovery

**Why:** a report proposes epics with an outcome, and its sources are there
