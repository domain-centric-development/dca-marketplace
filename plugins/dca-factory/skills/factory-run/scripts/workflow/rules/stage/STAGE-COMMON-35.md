---
id: STAGE-COMMON-35
part: told
why: compound commands, loops and absolute paths were refused one by one in unattended runs, each a lost turn
section: The shell a stage has
order: 35
---

# STAGE-COMMON-35

Every command is checked part by part before it runs, and nobody is there to grant one: a loop, a
variable or `$(…)`, a part outside that list and a path outside the project are refused, each a turn
spent. Run one plain command per call from the project root, never a `cd` to an absolute path; read
files with Read — several in parallel calls, never a loop over them. Every turn sends this whole
session again, so put the calls that do not wait for each other's result into one turn: the files you
read, the searches you run, the files you write that do not depend on one another.
