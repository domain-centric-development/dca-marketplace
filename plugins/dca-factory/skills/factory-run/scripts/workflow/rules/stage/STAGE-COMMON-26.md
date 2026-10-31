---
id: STAGE-COMMON-26
part: told
section: Ask, do not recall — but only a source the project named
marked: factory-run/reference/stage-common.md
order: 26
---

# STAGE-COMMON-26

**Never adopt a knowledge source the profile did not name.** A catalog that happens to be installed
may be a vendored copy of an older release: its rule ids, marker names and recipes can describe a
version the project does not use, and a citation makes that wrongness look verified. If you notice
such a skill, say so in your file — "`<skill>` is available but not named in the profile, so it was
not used" — and decide from the project's own rules, markers and documents instead. Those are the
source of truth; a catalog is a convenience the project has to vouch for.
