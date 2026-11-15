---
id: STAGE-FILES-9
part: told
why: a stage that could not finish would stop without a file, leaving the run nothing to read
section: Escalation
see: factory-run/reference/file-contracts.md
order: 1
---

# STAGE-FILES-9

A stage that cannot finish still writes its file, with `## needs-human`; the run stops there. Two situations always
escalate, never solved:
