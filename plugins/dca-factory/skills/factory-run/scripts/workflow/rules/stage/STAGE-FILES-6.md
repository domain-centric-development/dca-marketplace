---
id: STAGE-FILES-6
part: told
section: Review files — `.dca-factory/runs/<story>/reviews/<perspective>.md`
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-6

One file per perspective the judge covers: `ddd`, `hexagonal`, `clean-code` and whatever the profile's
`reviews:` adds, each written by the review skill `review.<perspective>:` names (`review-<perspective>`
where the profile names none), in that skill's report format — `## Findings` with `### must-fix`,
`### should-fix` and `### nits`, every finding with the file and line it stands on and a one-line fix,
"nothing found" said plainly. The runner starts the reviewers at once, before the judge, one process
each; a session starts one subagent each where the tool has them. The judge reads the files and
converges — confirms each finding in the code or drops it with the reason — and names the file per
perspective under `## Perspectives covered`. The document gate reads them as `reviews`: a missing file
is a note (the judge ran that pass itself and says so), a file without a findings section is refused.
A repeat round writes new files; the old ones are not kept. `--contract review` prints the shape.
