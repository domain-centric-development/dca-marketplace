---
id: GATE-INSTRUCTION-SIZE
part: check
reports:
- instruction-size
pass: `AGENTS.md` (or `CLAUDE.md`) is within 32 KiB
skip: it is larger — move detail into referenced files
---

# GATE-INSTRUCTION-SIZE

**When:** the plan gate

**Why:** an instruction file over 32 KiB is truncated without a word
