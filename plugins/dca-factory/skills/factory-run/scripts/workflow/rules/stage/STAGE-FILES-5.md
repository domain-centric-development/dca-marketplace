---
id: STAGE-FILES-5
part: told
section: A story's worktree — `.dca-factory/worktrees/<story>/`
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-5

The runner gives every story a git worktree of its own, on a branch `story/<id>` made from the main
checkout's branch, which `.dca-factory/evidence/<story>/target` records. Every stage runs there and
changes code there alone. What is state stays in the main checkout, and the worktree sees it through links
(on Windows junctions): the epics with the stories and their records, the run folder, the discovery
reports, the installed pipeline and the tools' skill folders; the product, technical and domain description
and the profile are copies, read alone. `FACTORY_HOME` names the main checkout to every process in the
worktree, so the gate and the cli read each place from there and leave those paths out of the story's
changes. `.dca-factory/worktrees/` is kept out of the main checkout's status in `.git/info/exclude`.
