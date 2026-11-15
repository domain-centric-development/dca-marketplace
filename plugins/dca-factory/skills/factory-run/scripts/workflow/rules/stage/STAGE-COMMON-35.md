---
id: STAGE-COMMON-35
part: told
why: compound commands, loops and absolute paths were refused one by one in unattended runs, each a lost turn
section: The shell a stage has
order: 35
---

# STAGE-COMMON-35

Every command is checked part by part: a loop, a variable or `$(…)`, an unlisted part, a path outside the project —
refused, a turn spent. One plain command per call from the project root, never `cd` to an absolute path. Read files
with Read, several in parallel, never in a loop. Each turn resends the whole session: batch independent reads,
searches and writes into one turn.
