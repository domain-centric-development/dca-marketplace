---
id: STAGE-BUILD-3
part: told
stages:
- build
section: Do
marked: stage-build/SKILL.md
order: 4
---

# STAGE-BUILD-3

3. Keep the architecture intact — the same rules the plan worked under: no framework types in the
   domain, ports declared inward and implemented in adapters, no raw cross-context imports, one
   aggregate per transaction, domain events published and cleared where the plan says so.
