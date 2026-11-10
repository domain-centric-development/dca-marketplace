---
id: STAGE-FILES-8
part: told
why: a test that flaked across stories belonged to none of them and had no place to be tracked
section: Project findings — `product/findings/<name>.md`, beside the epics
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-8

A finding that belongs to no one story, in the same table and with the same `Status`, in a file of the project's own
beside the epics (`findings/` next to the epics' folder). One kind today: `flaky.md` — a test the build, tidy or
integrate gate ran again alone and saw green (`flaky=` on the journal's gate line, WP-113) in two stories becomes one
open row there, written by the delivering gate and committed with its delivery; one open row per test. A row is named
`<name>#<n>` — `flaky#3` — which is what a task's `closes:` names; the status lists the rows beside the stories'
(`findings`, with `row` and `project`), and the inbox hands a row to the backlog skill by that name. A story's own
id wins where a story is named like such a file. The folder is linked into a story's worktree like the epics.
