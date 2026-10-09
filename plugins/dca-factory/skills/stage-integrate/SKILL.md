---
name: stage-integrate
description: Integrate step of a factory run — resolves the merge conflicts between a story's worktree and the main line it is integrated into, so that both changes hold. Use when the runner's integrate step found conflicts, when the orchestrator hands over a list of conflicted files, or on "/stage-integrate". Edits only the conflicted files and commits nothing. Internal step of the pipeline — the runner starts it; by hand only to resolve one story's conflicts again.
---

# Resolve one story's merge conflicts

Input: the story, `.dca-factory/runs/<story>/plan.md`, `.dca-factory/runs/<story>/.verify/conflicts` — the files git
could not merge — and the two sides as git shows them (`git diff`, `git log`). Nothing else.
Output: the conflicted files with every conflict resolved, plus `.dca-factory/runs/<story>/integrate.md`.

Every story runs in a worktree of its own and reaches the main line only when it is integrated: the runner
merges the main line into the story's branch and squashes the story to one commit. Most merges need no hand.
Where two stories changed the same lines — the same glossary section, the same aggregate, the same page — git
stops and names the files. This step makes both changes true; it is not a choice between them.

## Do

1. Read the story and its plan, then every file the conflicts list names. Between `<<<<<<<` and `=======` is
   the story's side, between `=======` and `>>>>>>>` the main line's. `git log --oneline -5 <target>` and
   `git diff <target>...HEAD -- <file>` show what each side meant.
2. Keep both. The main line carries what another story delivered and a person accepted: its behaviour stays.
   The story's change goes on top of it, in the shape the main line has now — a renamed method is called by
   its new name, a glossary entry the other story added stays beside this story's.
3. Remove every conflict marker. A file with one left is refused, and the integrate gate searches every file
   the story's commit changes.
4. Edit nothing outside the conflicted files. A test that the merged code would now fail is the integrate
   gate's finding and goes back to the build stage; this step does not chase it.
5. Run no `git add`, `git commit`, `git merge`, `git rebase` or `git checkout`: the runner commits the
   resolution, squashes the story and holds it to the gate once more.
6. Where both sides cannot hold — the main line removed what the story builds on, two rules contradict —
   stop with a `## needs-human` section and a decision record (`factory-run/reference/stage-common.md`).

## The integrate file

```markdown
# Integrate — <story id>

| File | The story changed | The main line changed | How both hold |
|---|---|---|---|
```

One row per conflicted file. The gate's outcome is not recorded here: its report is the evidence.

## Do not

- Do not take one side whole to make a conflict go away.
- Do not reformat, rename or tidy anything a conflict does not need.
