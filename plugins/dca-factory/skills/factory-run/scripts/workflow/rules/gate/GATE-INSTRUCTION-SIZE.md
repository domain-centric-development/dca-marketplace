---
id: GATE-INSTRUCTION-SIZE
title: The instruction file stays within 32 KiB
part: check
reports:
- instruction-size
pass: `AGENTS.md` (or `CLAUDE.md`) is within 32 KiB
skip: the file is larger — detail has to move into referenced files
---

# GATE-INSTRUCTION-SIZE

**When:** the plan gate runs

**Why:** an instruction file over 32 KiB is truncated without a word
