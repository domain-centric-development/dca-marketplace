---
id: RUN-TOOL-1
title: A unit gets the most specific tool the profile names
part: decision
pass: the tool comes from `--tool` or `FACTORY_TOOL_CMD`, else `tool.<unit>`, else `tool`, else the run's tool, and every tool is on the PATH before the first stage (else exit 2)
---

# RUN-TOOL-1

**When:** a unit is dispatched — the builder, the verifier, a review, a stage, a request

**Why:** the tool is the most specific the profile names
