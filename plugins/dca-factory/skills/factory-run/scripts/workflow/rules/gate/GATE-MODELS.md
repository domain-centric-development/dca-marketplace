---
id: GATE-MODELS
part: check
reports:
- models
pass: every `model` key names a tool and a stage it knows
fail: a key without a tool, an unknown tool or stage, or an empty value
---

# GATE-MODELS

**When:** the plan gate, where the profile names models

**Why:** a model key nobody reads is a silent default
