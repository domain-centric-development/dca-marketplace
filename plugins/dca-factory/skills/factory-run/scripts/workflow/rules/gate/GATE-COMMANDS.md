---
id: GATE-COMMANDS
title: The architecture and format commands pass
part: check
reports:
- architecture
- format
pass: the command exits 0
fail: the command fails — its output is quoted
skip: the profile declares no such command
---

# GATE-COMMANDS

**When:** a gate runs whose stage names profile commands (build, tidy, integrate: architecture and format; document: architecture)

**Why:** the architecture suite and the formatter hold every change
