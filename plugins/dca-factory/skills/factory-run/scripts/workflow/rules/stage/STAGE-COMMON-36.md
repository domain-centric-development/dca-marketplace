---
id: STAGE-COMMON-36
part: told
why: later stages and the format check found files an earlier stage had left unformatted
section: The formatter runs last
order: 36
---

# STAGE-COMMON-36

`formatFix:` declared → run it last, before you finish (`GATE-COMMANDS` checks `format:`). A file it touches that the
story never changed: the change record names it, the judge reads it as a finding.
