---
id: STAGE-FILES-9
part: told
why: a stage that could not finish would stop without a file, leaving the run nothing to read
section: Escalation
see: factory-run/reference/file-contracts.md
order: 1
---

# STAGE-FILES-9

A stage that cannot finish writes its file anyway, with a `## needs-human` section, and the
orchestrator stops the run at that point. Two situations always escalate rather than being solved:
