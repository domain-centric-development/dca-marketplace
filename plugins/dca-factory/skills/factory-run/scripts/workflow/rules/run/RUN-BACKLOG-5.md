---
id: RUN-BACKLOG-5
title: One failing story does not hold the rest
part: decision
pass: the story fails — it and its dependants are skipped and the others run on
fail: the failure is exit 2 or 5, or `--max-stages` is reached — it is never skipped
---

# RUN-BACKLOG-5

**When:** a story fails under `--keep-going`

**Why:** one failing story does not hold the rest
