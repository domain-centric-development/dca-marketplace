---
id: STAGE-COMMON-24
part: told
section: A review the runner started
marked: factory-run/reference/stage-common.md
---

# STAGE-COMMON-24

A prompt that says *Review the change … from the <perspective> perspective* names the review skill, the
diff, its inputs and the report's path. Apply the skill to the diff — open a whole file only where the
diff's context does not carry the question. Write the report in the skill's own format: `## Findings`
with must-fix, should-fix and nits, every finding with the file and line it stands on and a one-line
fix; say plainly when you found nothing. Change no other file and no code; you are one of several
reviewers, a judge reads the reports.
