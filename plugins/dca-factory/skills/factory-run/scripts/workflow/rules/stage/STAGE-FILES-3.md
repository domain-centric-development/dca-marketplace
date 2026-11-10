---
id: STAGE-FILES-3
part: told
why: a stage could write the marks and records that prove its own work
section: One owner per place — the story carries its state, the run folder is protocol
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-3

`.dca-factory/runs/<story>/` holds what the stages hand over: the hand-overs, their skeletons, a gate's
refusal. What proves a stage's work lies beside it, in `.dca-factory/evidence/<story>/`: the marks
(`.story-digest`, `.tests-red`, `.tests-baseline`, `.rounds`), the journal, the snapshots, the changed-files
records, the base tree and the tools' output. The gate and the runner write the evidence folder; a stage reads
it and never writes there — the runner names it to no tool as a folder to write. `.owned-digest` holds, while a
stage window is open, the digest of what is the person's — the story file and every decision's `## Answer`; the
window's end compares, and a change leaves `.owned-changed`: the story is stopped and the gate refuses (`owned`)
until `factory-cli.py --owned-confirm <story>`. The gate's own writes (delivered, reopened, `## Applied`) are
not a change. Nothing the factory needs
*after* a run lives in either, but the journal: the install keeps `.dca-factory/` out of git but for
`<evidence>/<story>/journal.tsv` (`/.dca-factory/*` and the lines that let the journals in; a project whose
`.gitignore` names the folder in a line of its own other than `/.dca-factory` keeps its lines), and the commit
hook's snapshot leaves both folders out. Whether a story is delivered stands
in the story itself: the gate that delivers — the document gate, the adopt gate, or in a story's worktree the
integrate gate, all through one function — writes `status: delivered`, `delivered: <UTC time>` and
`delivered_by: gate` into its front matter when it passes; built or adopted, the three lines are the same (one
end state). No stage and no skill writes them; `draft → approved` is the person's, `→ delivered` the gate's — or
a person's who delivered the story by hand (`delivered_by: hand:<who>`, `--deliver-by-hand`), a claim the views
show as such until `--prove` has the adopt path check it. The plan gate's story digest leaves the three lines
out — the front matter read by lines, a `---` inside a line is text — so a delivery never reads as "the story
changed after it was planned". When the gate stamps an answer `## Applied`, it writes the answer into the story
as an `answered:` line under `## Assumptions` and takes the planned digest anew in the same write; any other
change after plan still re-plans. A reopen (`--reopen`, on an answered
correction the story cites) takes the lines out again and moves the delivered pass's hand-overs to
`.dca-factory/evidence/<story>/pass-<n>/`, so the first pass stays readable beside the next.
