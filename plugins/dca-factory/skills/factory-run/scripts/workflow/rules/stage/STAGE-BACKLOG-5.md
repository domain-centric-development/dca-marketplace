---
id: STAGE-BACKLOG-5
part: told
section: Task
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/backlog-contract.md
---

# STAGE-BACKLOG-5

`kind: task` in a story's front matter makes it a change no actor sees: a refactoring, a judge's finding that
changes no behaviour, a dependency or build change, a unit test for an invariant that already holds. It has **no**
acceptance criteria — a criterion is behaviour, and behaviour that changes is a story with a red test; the plan gate
refuses a task with one. What it does stands in the body, in a sentence or two. `closes:` names the finding rows it
settles, `<story>#<n>` (the row's number in that story's `findings.md`) or `<name>#<n>` for a project finding
(`product/findings/<name>.md`, such as `flaky#1`), each open; the delivering gate sets them to `done`. It runs plan, build, tidy, judge and document — no test stage —, and its evidence is the existing suite: the
build and tidy gates run every test command the profile declares, whole, with the architecture and format checks; a
test that existed before the task may not change (`tests-kept`), a new one may be added. No spec delta: what holds is
what held. Taking a feature away is not a task — an actor sees it gone — but a story whose criterion is the absence.
