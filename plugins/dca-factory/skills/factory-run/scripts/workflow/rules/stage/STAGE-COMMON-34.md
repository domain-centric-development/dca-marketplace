---
id: STAGE-COMMON-34
part: told
section: The shell a stage has
marked: factory-run/reference/stage-common.md
---

# STAGE-COMMON-34

The runner lets a stage run, without asking, the gate, the cli, the commands the stack profile declares,
and the ordinary reading tools — `cd`, `ls`, `cat`, `head`, `tail`, `wc`, `sort`, `grep`, `diff`, `pwd`, and
`git status`, `git diff`, `git log`, `git ls-files`, `git apply --check` (how a break patch is tried), and
`git rm` — how a file the plan's `## Files` says `removed` goes; the prompt names the list. Nothing else that writes: list files with Glob, search with Grep, write with Write (it makes the folders). Everything else asks, and in an unattended run nobody answers:
the call is refused and the turn is lost. A file is changed with the editor tools, never with a script
fed on stdin (`python3 -` and a heredoc) — that is the one habit the bench saw refused three times per
story. In a session the same tools are the ones a person answers "yes" to without looking twice.
