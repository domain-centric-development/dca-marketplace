---
id: STAGE-FILES-1
part: told
why: stages reconstructed what a story changed themselves and got it wrong
section: What changed — `.dca-factory/evidence/<story>/changed-<stage>.txt`, `changed.txt`, `story.diff`
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-1

The pipeline records what a story changes; no stage reconstructs it. Around every stage the
runner — or `--stage-start`/`--stage-end` in a session — observes the working tree once at the stage's
start and once at its end, one file per edge (`tree-before-<stage>.txt`, `tree-after-<stage>.txt`):
HEAD, every file git reports as differing from HEAD with its sha256 (a tracked file that is gone as
`deleted`, the untracked ones after a line `# untracked`), and at the end the tree object of everything
as it is. After the stage the gate writes, from those two observations alone, `changed-<stage>.txt`
(`added` / `modified` / `removed` and a path, one per line), and the story's cumulative `changed.txt`
and `story.diff` against the tree observed at the story's first stage — written once, without committing, so a
repository without a commit gets a diff as well and a stage run again does not move the story's
starting point. Paths are the project's, also where the project is a directory inside a larger
repository. The run folder, the installed pipeline (`.agents/factory/`), a story's `decisions/` records and gitignored files are left out. Without
git the tree cannot be compared: the observations and the records then carry one line, `# not observed:`
and the reason, `story.diff` says there is no diff, and the gate skips the files check and names the
reason — never "0 files changed".
