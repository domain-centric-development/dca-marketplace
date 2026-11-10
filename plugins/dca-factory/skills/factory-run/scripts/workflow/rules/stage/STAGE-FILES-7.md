---
id: STAGE-FILES-7
part: told
why: the judge's minor findings vanished once a story was delivered
section: Findings — `<story>/findings.md`, in the story's folder
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-7

The judge's confirmed defects that did not block the story — its minors — written by the document gate when it
delivers the story, from `judge.md`'s `## Confirmed defects` table (`| Perspective | File:line | Severity | In plain
words | Defect | Fix |`): one row per finding, `| # | Perspective | File:line | Severity | In plain words | Defect |
Fix | Status |`, `Status` `open`; a row already there (same file:line and defect) is not written twice. `In plain
words` is the one sentence a person reads first — the status JSON's `plain`, which the inbox leads with; a judge
row without it is a note at delivery. A judge table or a findings file from before contract 23 has no such column:
it is read with the sentence empty, and a findings file gains the empty column when the next row is added to it. The file lives in the story's folder beside its `decisions/`, is committed with the project
and is no story to the backlog. A person sets `done` or `wont-fix`; a later story may take the open rows as its
brief. `factory-cli.py --findings` lists the open rows, and the status brief counts them.
