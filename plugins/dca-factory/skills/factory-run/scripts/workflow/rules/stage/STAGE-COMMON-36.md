---
id: STAGE-COMMON-36
part: told
section: The formatter runs last
marked: factory-run/reference/stage-common.md
---

# STAGE-COMMON-36

Where the stack profile declares `formatFix:`, run it last, before you finish: it corrects the
formatting of what you wrote, so the stages after you find their own files as the formatter wants
them. The gate and the commit hook only check `format:` and change no file. A file the formatter
touches that this story never changed is not yours to keep quiet about — the pipeline's record of
what changed names it, and the judge reads it as the finding it is.
