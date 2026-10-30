---
id: RUN-BACKLOG-5
part: decision
pass: it and its dependants are skipped, the others run on
fail: never for exit 2, 5, or a reached `--max-stages`
---

# RUN-BACKLOG-5

**When:** a story fails under `--keep-going`

**Why:** one failing story does not hold the rest
