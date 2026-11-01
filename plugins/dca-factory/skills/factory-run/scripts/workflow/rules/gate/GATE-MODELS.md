---
id: GATE-MODELS
title: Every model key names a known tool and stage
part: check
reports:
- models
pass: every `model` key names a tool and a stage it knows
fail: a key has no tool, a tool or stage is unknown, or a value is empty
---

# GATE-MODELS

**When:** the plan gate runs, where the profile names models

**Why:** a model key nobody reads is a silent default
