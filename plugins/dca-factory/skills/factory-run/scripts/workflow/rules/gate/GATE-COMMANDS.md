---
id: GATE-COMMANDS
part: check
reports:
- architecture
- format
pass: the command exits 0
fail: it fails — its output quoted
skip: the profile declares no such command
---

# GATE-COMMANDS

**When:** the gates whose stage names profile commands (build, tidy, integrate: architecture and format; document: architecture)

**Why:** the architecture suite and the formatter hold every change
