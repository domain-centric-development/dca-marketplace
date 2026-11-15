---
id: STAGE-COMMON-34
part: told
why: unattended stages lost turns on commands the runner refused, scripts fed on stdin above all
section: The shell a stage has
order: 34
---

# STAGE-COMMON-34

Allowed without asking (the prompt lists them): the gate, the cli, the profile's commands, `cd`, `ls`, `cat`, `head`,
`tail`, `wc`, `sort`, `grep`, `diff`, `pwd`, `git status`, `git diff`, `git log`, `git ls-files`, `git apply --check`
(trying a break patch), `git rm` (a file the plan marks `removed`). List with Glob, search with Grep, write with Write.
Anything else is refused unattended and the turn is lost. Change files with the editor tools, never a script on stdin
(`python3 -` with a heredoc) — refused three times per story on the bench.
